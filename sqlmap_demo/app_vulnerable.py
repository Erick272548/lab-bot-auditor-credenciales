"""
app_vulnerable.py - API con una inyeccion SQL PUESTA A PROPOSITO (laboratorio)
=============================================================================

ADVERTENCIA: este archivo contiene una vulnerabilidad DELIBERADA para
demostrar sqlmap en un entorno controlado y local. NO es como se debe
programar. El codigo correcto (consultas parametrizadas) esta en
etapas/commit1/database.py.

Se conecta a la base `lab_usuarios` del MySQL de XAMPP (puerto 3350) y
expone dos versiones del mismo buscador para comparar:

  GET /usuarios/buscar?nombre=...   -> INSEGURO: concatena el parametro en el SQL
  GET /usuarios/buscar_seguro?nombre=...  -> SEGURO: consulta parametrizada

Levantar:
    python app_vulnerable.py          # http://127.0.0.1:5002
"""
from flask import Flask, jsonify, request
import pymysql
from pymysql.cursors import DictCursor

app = Flask(__name__)

# Credenciales FICTICIAS del laboratorio (las mismas que se "filtran" en la otra demo)
CONEXION = dict(
    host="127.0.0.1", port=3350, user="lab_app",
    password="Pr0y3ct0_T3st_2026!", database="lab_usuarios",
    charset="utf8mb4", cursorclass=DictCursor, autocommit=True,
)


def conectar():
    return pymysql.connect(**CONEXION)


@app.get("/salud")
def salud():
    return jsonify(estado="ok", servicio="api-vulnerable-laboratorio")


@app.get("/usuarios/buscar")
def buscar_vulnerable():
    """INSEGURO - el valor de 'nombre' se concatena directo en la consulta."""
    nombre = request.args.get("nombre", "")
    # VULNERABILIDAD DELIBERADA (CWE-89): nunca hacer esto en produccion.
    sql = f"SELECT id, nombre, email FROM usuarios WHERE nombre LIKE '%{nombre}%'"
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(sql)
        filas = cur.fetchall()
    return jsonify(consulta=sql, resultados=filas)


@app.get("/usuarios/buscar_seguro")
def buscar_seguro():
    """SEGURO - consulta parametrizada; sqlmap NO la inyecta."""
    nombre = request.args.get("nombre", "")
    sql = "SELECT id, nombre, email FROM usuarios WHERE nombre LIKE %s"
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(sql, (f"%{nombre}%",))
        filas = cur.fetchall()
    return jsonify(resultados=filas)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=False)
