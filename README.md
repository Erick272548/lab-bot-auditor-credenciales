# Laboratorio de caja blanca: fuga de credenciales en Git y bot de monitoreo

> **Práctica académica en entorno controlado.** Todas las contraseñas, tokens y
> llaves de este laboratorio son **100 % ficticias**. El repositorio objetivo
> es propio y se hizo público a propósito para la demostración.

Demuestra que un bot que vigila un repositorio público captura credenciales
expuestas aunque el desarrollador las borre minutos después.

| Componente | Dónde |
|---|---|
| Bot auditor | [`bot_monitor/repo_watcher.py`](bot_monitor/repo_watcher.py) (este repo) |
| Proyecto ficticio (objetivo) | https://github.com/Erick272548/lab-proyecto-ficticio-fuga |
| Código exacto de cada commit | [`etapas/commit1`](etapas/commit1), [`etapas/commit2`](etapas/commit2), [`etapas/commit3`](etapas/commit3) |
| Script que ejecuta los 3 commits | [`simular_fuga.py`](simular_fuga.py) |
| Evidencia de la ejecución real | [`evidencia/`](evidencia) |
| Demo extra de inyección SQL con sqlmap | [`sqlmap_demo/`](sqlmap_demo) |

```
lab_fuga_credenciales/            (C:\xampp5001\htdocs\lab_fuga_credenciales)
├── bot_monitor/
│   ├── repo_watcher.py           bot auditor (solo biblioteca estándar)
│   ├── .repo_cache/              clon oculto (se genera)
│   ├── Respaldos_Repo/           una carpeta por commit (se genera)
│   └── alertas_seguridad.log     alertas (se genera)
├── proyecto_ficticio/            repo Git del proyecto (lo crea simular_fuga.py)
├── etapas/commit1|2|3/           archivos de cada commit
├── bd/setup_mysql.sql            base y usuario en el MySQL de XAMPP
├── simular_fuga.py
└── evidencia/                    salida real del bot y de la simulación
```

---

## Puesta en marcha (XAMPP local)

1. Iniciar **MySQL** desde el panel de XAMPP (`C:\xampp5001`, puerto **3350**).
2. Crear base y usuario del laboratorio:
   ```
   C:\xampp5001\mysql\bin\mysql.exe -u root -P 3350 -h 127.0.0.1 < bd\setup_mysql.sql
   ```
3. Dependencias del proyecto ficticio: `pip install -r etapas/commit1/requirements.txt`
   (el bot no necesita ninguna).
4. Terminal 1, el bot:
   ```
   cd bot_monitor
   python repo_watcher.py https://github.com/Erick272548/lab-proyecto-ficticio-fuga.git
   ```
5. Terminal 2, la simulación (sobre un repositorio público vacío):
   ```
   python simular_fuga.py https://github.com/USUARIO/REPO_VACIO.git --pausa 45
   ```
6. Probar la API: `cd proyecto_ficticio`, `copy .env.example .env`, rellenar y `python app.py`
   (http://127.0.0.1:5001).

---

## Parte 1. El bot auditor

`repo_watcher.py` usa solo `subprocess`, `shutil`, `pathlib`, `time`, `re`
(y `json`, `hashlib`, `argparse`, `os`, `stat`, `datetime`, también estándar).

| Requisito | Implementación |
|---|---|
| Polling de `main` cada 15 s, URL configurable | argumento `repo_url` o variable `REPO_URL`; `--intervalo 15` |
| Clon oculto | `.repo_cache/` (atributo oculto en Windows) + `git fetch` en cada ciclo |
| Recorrer **todos** los commits nuevos en orden | `git rev-list --reverse origin/main`, filtrando los ya procesados (`.estado_bot.json`); también funciona tras un *force-push* |
| Copia por commit sin `.git` | `git checkout --detach <sha>` + `shutil.copytree(..., ignore=ignore_patterns(".git"))` en `Respaldos_Repo/AAAA-MM-DD_HH-MM-SS_<hash>` |
| Copias inmutables | archivos en solo lectura + `_EVIDENCIA_COMMIT.txt` con autor, mensaje, cambios y SHA-256 de cada archivo |
| Escaneo con `re` | archivos `.env*` (no plantillas) → **CRÍTICO**; variables `PASSWORD`, `PASS`, `SECRET`, `API_KEY`, `TOKEN`, `ACCESS_KEY` con valor literal → **ALTO**; ignora `os.getenv(...)` y valores vacíos |
| Alertas | consola + `alertas_seguridad.log`; valores enmascarados (`Pr0y****`) |
| Borrado posterior | si un commit borra un archivo que ya tenía hallazgos → **AVISO**: sigue en el historial, hay que rotar |

---

## Parte 2. Secuencia de 3 commits

El código completo de cada archivo está en `etapas/`. Comandos ejecutados
(los hace `simular_fuga.py`):

### Commit 1 – Versión limpia
`app.py`, `database.py`, `config.py`, `requirements.txt`, `.gitignore`, `README.md`.
`config.py` solo lee del entorno:
```python
DB_USER = os.getenv("DB_USER", "")
DB_PASS = os.getenv("DB_PASS", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
```
El desarrollador tiene un `.env` local, pero `.gitignore` lo excluye.
```
git init -b main
git remote add origin https://github.com/Erick272548/lab-proyecto-ficticio-fuga.git
git add .
git commit -m "Estructura base de la API de usuarios"
git push -u origin main
```

### Commit 2 – Fuga accidental
`config.py` con valores escritos en el código y `.env` forzado con `-f`:
```python
DB_USER = "lab_app"
DB_PASS = "Pr0y3ct0_T3st_2026!"
JWT_SECRET = "clave_jwt_ficticia_para_laboratorio"
MAIL_API_KEY = "sk-test-ficticia-987654321"
PAGOS_API_KEY = "pk_lab_ficticia_000111222333"
```
```
git add config.py
git add -f .env
git commit -m "Configurar conexion para la demo"
git push origin main
```

### Commit 3 – Intento de borrado
```
git rm .env
(config.py vuelve a os.getenv(...) y se agrega .env.example vacío)
git add config.py .env.example
git commit -m "Eliminar .env y mover credenciales a variables de entorno"
git push origin main
```

---

## Resultado de la ejecución real

Ejecución del 23 de noviembre de 2026 contra
https://github.com/Erick272548/lab-proyecto-ficticio-fuga (bot con polling de 15 s,
45 s entre commits). Salida completa en [`evidencia/`](evidencia).

| Commit | Hora del commit | Respaldado por el bot | Resultado del escaneo |
|---|---|---|---|
| `153fc98` Estructura base | 00:52:18 | 00:52:23 | sin hallazgos |
| `6377521` Configurar conexión (fuga) | 00:53:05 | **00:53:11** | 1 CRÍTICO + 11 ALTO |
| `3fddca4` Eliminar .env | 00:53:53 | 00:53:58 | sin hallazgos + **AVISO**: el `.env` ya fue capturado |

Extracto de [`evidencia/alertas_seguridad.log`](evidencia/alertas_seguridad.log):
```
[CRITICO] commit 6377521 | .env | archivo de entorno .env versionado en el repositorio
[ALTO] commit 6377521 | .env:6 | DB_PASS con valor en texto plano: Pr0y************
[ALTO] commit 6377521 | .env:9 | JWT_SECRET con valor en texto plano: clav************
[ALTO] commit 6377521 | config.py:18 | DB_PASS con valor en texto plano: Pr0y************
...
[AVISO] commit 3fddca4 borra '.env', pero su contenido ya fue capturado del commit 6377521
        y sigue en el historial de Git. Las credenciales deben ROTARSE.
```
La copia íntegra del commit de la fuga, `.env` incluido, quedó en
[`evidencia/Respaldos_Repo/2026-11-23_00-53-05_6377521`](evidencia/Respaldos_Repo/2026-11-23_00-53-05_6377521).

---

## Análisis de caja blanca

### 1. Hallazgos críticos en el código del Commit 2 (`6377521`)

| # | Hallazgo | Ubicación | Severidad | CWE |
|---|---|---|---|---|
| 1 | Archivo `.env` versionado; se saltó `.gitignore` con `git add -f` | `.env` | Crítica | CWE-538 |
| 2 | Contraseña de la base de datos en texto plano (`lab_app` / `DB_PASS`) | `config.py:18`, `.env:6` | Crítica | CWE-798 |
| 3 | Contraseña del usuario root de MySQL | `.env:7` | Crítica | CWE-798 |
| 4 | Secreto de firma JWT en el código | `config.py:21`, `.env:9` | Crítica | CWE-321 |
| 5 | Llaves de servicios externos (correo, pagos, almacenamiento) | `config.py:25-26`, `.env:12-15` | Alta | CWE-798 |
| 6 | Datos de conexión completos (host, puerto 3350, base, usuario) | `config.py`, `.env` | Media | CWE-200 |

Impacto, leyendo el código de `app.py` y `database.py`:

- **`JWT_SECRET`**: `requiere_token` solo comprueba la firma HS256 con esa
  clave. Quien la tenga puede fabricar un token válido para cualquier `sub`
  y usar `GET /usuarios` y `DELETE /usuarios/<id>` sin contraseña.
- **`DB_USER`/`DB_PASS`**: `lab_app` tiene `ALL PRIVILEGES` sobre
  `lab_usuarios`; con acceso al puerto se leen o borran todos los usuarios y
  sus hashes. Con la de root, todo el servidor MySQL.
- **Llaves externas**: envío de correos a nombre de la empresa, cargos o
  lectura de archivos; con costo y daño de reputación.
- **Causa raíz**: secretos en el código fuente, uso de `git add -f`, sin
  revisión previa (*pre-commit hook* o escáner de secretos) ni gestor de secretos.

### 2. Por qué el Commit 3 no remedia la vulnerabilidad

1. **Git guarda historia, no solo el estado actual.** Cada commit apunta a
   un árbol completo de archivos (*blobs* identificados por su hash). El
   commit 3 crea un árbol nuevo sin `.env`, pero el commit 2 y su *blob*
   siguen existiendo y son su padre. Cualquiera que clone el repo los tiene:
   ```
   git log --oneline --all -- .env
   git show 6377521:.env
   git show 6377521:config.py
   ```
2. **GitHub los sigue sirviendo.** La URL del commit 2 sigue abierta en
   GitHub (https://github.com/Erick272548/lab-proyecto-ficticio-fuga/commit/6377521). Aunque se reescriba el historial con
   `git filter-repo` y `git push --force`, el commit puede quedar visible por
   su SHA, en *forks*, cachés y en la API de eventos hasta que GitHub lo purgue.
3. **La captura es automática y rápida.** Los bots consultan la API de eventos
   públicos de GitHub o hacen *polling* como `repo_watcher.py`. Nuestro bot
   respaldó el commit 2 **unos 6 segundos** después del commit, mucho
   antes que el commit 3 (48 s después). Además, como recorre
   `git rev-list --reverse`, lo habría capturado aunque el commit 2 y el 3 se
   subieran juntos en un solo push: la copia en `Respaldos_Repo/` ya no
   depende del repositorio.
4. **Conclusión:** en cuanto un secreto llega a un repositorio público, se da
   por comprometido. La remediación correcta es, en este orden:
   - **rotar o revocar** cada credencial (nueva contraseña de BD, nuevo
     `JWT_SECRET`, que invalida todos los tokens, y nuevas llaves externas);
   - después, limpiar el historial (`git filter-repo --path .env --invert-paths`
     y reemplazar los literales de `config.py`), hacer *force-push* y pedir a
     GitHub que purgue las vistas en caché;
   - prevenir: `.gitignore` sin `-f`, escáner de secretos en *pre-commit* y en
     CI (gitleaks, trufflehog), *push protection* de GitHub y un gestor de secretos.
