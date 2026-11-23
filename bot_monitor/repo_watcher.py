"""
repo_watcher.py - Bot auditor de repositorios (laboratorio de caja blanca)
=========================================================================

Vigila la rama `main` de un repositorio Git publico y guarda una copia
inmutable de CADA commit nuevo, en orden cronologico. Despues escanea cada
copia con expresiones regulares en busca de credenciales expuestas.

Demuestra por que borrar un secreto en un commit posterior no sirve:
el bot recorre todos los commits intermedios (git rev-list --reverse),
asi que el estado en el que el secreto estaba presente queda respaldado.

Solo usa la biblioteca estandar de Python (subprocess, shutil, pathlib,
time, re, json, hashlib, argparse, datetime, os, stat).

Uso:
    python repo_watcher.py https://github.com/USUARIO/REPO.git
    python repo_watcher.py URL --intervalo 15 --una-vez
    set REPO_URL=https://github.com/USUARIO/REPO.git && python repo_watcher.py

USO EXCLUSIVO EN ENTORNO CONTROLADO Y SOBRE REPOSITORIOS PROPIOS.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------------
# Configuracion
# ----------------------------------------------------------------------------
REPO_URL_POR_DEFECTO = os.getenv(
    "REPO_URL", "https://github.com/Erick272548/lab-proyecto-ficticio-fuga.git"
)
RAMA = "main"
INTERVALO_SEGUNDOS = 15

BASE = Path(__file__).resolve().parent
CACHE = BASE / ".repo_cache"                 # clon oculto
RESPALDOS = BASE / "Respaldos_Repo"          # una carpeta por commit
LOG_ALERTAS = BASE / "alertas_seguridad.log"
ESTADO = BASE / ".estado_bot.json"           # commits ya procesados

# False = en consola y log solo se ve el inicio del valor (buena practica).
# La copia completa siempre queda en Respaldos_Repo/.
MOSTRAR_SECRETOS_COMPLETOS = False

TAMANO_MAXIMO_ARCHIVO = 1_000_000  # bytes; archivos mayores no se escanean
EXTENSIONES_CODIGO = {".py", ".js", ".ts", ".php", ".java", ".go", ".rb", ".cs"}

# ----------------------------------------------------------------------------
# Patrones de deteccion (re)
# ----------------------------------------------------------------------------
# Archivos de entorno: .env, .env.local, .env.production ... (no plantillas)
PATRON_ARCHIVO_ENV = re.compile(r"^\.env(\.[\w-]+)?$", re.IGNORECASE)
PLANTILLAS_ENV = re.compile(r"\.(example|sample|template|dist)$", re.IGNORECASE)

# Nombre de variable sospechoso: PASSWORD, PASS, SECRET, API_KEY, TOKEN...
_NOMBRE = (
    r"[A-Za-z0-9_.]*(?:PASSWORD|PASSWD|PASS|PWD|SECRET|API_?KEY|TOKEN|"
    r"ACCESS_?KEY|PRIVATE_?KEY)[A-Za-z0-9_.]*"
)
# Asignacion con valor literal entre comillas:  DB_PASS = "valor"
PATRON_ASIGNACION_CON_COMILLAS = re.compile(
    rf"(?i)\b(?P<nombre>{_NOMBRE})\b\s*[:=]\s*(?P<q>['\"])(?P<valor>[^'\"]+)(?P=q)"
)
# Asignacion sin comillas (estilo .env):  DB_PASS=valor
PATRON_ASIGNACION_ENV = re.compile(
    rf"(?i)^\s*(?:export\s+)?(?P<nombre>{_NOMBRE})\s*=\s*(?P<valor>[^\s#'\"]+)"
)
# Valores que NO son secretos: lecturas de entorno o marcadores de posicion
PATRON_NO_SECRETO = re.compile(
    r"(?i)(getenv|environ|\(|\$\{|^<.*>$|^x+$|^\*+$|cambiar|changeme|your_|tu_|"
    r"placeholder|^none$|^null$|^true$|^false$)"
)
# Cadenas con forma de llave aunque la variable tenga otro nombre
PATRON_FORMA_DE_LLAVE = re.compile(r"\b(?:sk|pk|rk)[-_](?:test|live|lab)[-_][\w-]{6,}")


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def git(*args, cwd=CACHE, verificar=True):
    """Ejecuta git y regresa stdout como texto."""
    resultado = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if verificar and resultado.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} fallo:\n{resultado.stderr.strip()}")
    return resultado.stdout.strip()


def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def registrar(nivel, mensaje):
    """Imprime en consola y agrega la linea a alertas_seguridad.log."""
    linea = f"[{ahora()}] [{nivel}] {mensaje}"
    print(linea, flush=True)
    if nivel in ("CRITICO", "ALTO", "AVISO"):
        with LOG_ALERTAS.open("a", encoding="utf-8") as log:
            log.write(linea + "\n")


def enmascarar(valor):
    if MOSTRAR_SECRETOS_COMPLETOS or len(valor) <= 4:
        return valor
    return valor[:4] + "*" * min(len(valor) - 4, 12)


def cargar_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {"procesados": [], "archivos_con_hallazgos": {}}


def guardar_estado(estado):
    ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")


def solo_lectura(carpeta):
    """Marca todos los archivos del respaldo como solo lectura (inmutables)."""
    for archivo in carpeta.rglob("*"):
        if archivo.is_file():
            os.chmod(archivo, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


# ----------------------------------------------------------------------------
# Clon oculto y deteccion de commits nuevos
# ----------------------------------------------------------------------------
def preparar_cache(repo_url):
    if (CACHE / ".git").exists():
        return
    registrar("INFO", f"Clonando {repo_url} en {CACHE.name}/ ...")
    git("clone", "--quiet", repo_url, str(CACHE), cwd=BASE)
    if os.name == "nt":  # carpeta oculta en Windows
        subprocess.run(["attrib", "+h", str(CACHE)], capture_output=True)


def commits_nuevos(estado):
    """Descarga la rama y regresa los commits no procesados, del mas viejo al mas nuevo."""
    try:
        git("fetch", "--quiet", "origin", f"+refs/heads/{RAMA}:refs/remotes/origin/{RAMA}")
    except RuntimeError as error:
        if "couldn't find remote ref" in str(error):
            registrar("INFO", f"La rama '{RAMA}' aun no existe en el remoto; esperando...")
            return []
        raise
    todos = git("rev-list", "--reverse", f"origin/{RAMA}").splitlines()
    vistos = set(estado["procesados"])
    # Se compara contra el conjunto de vistos (y no contra "el ultimo"), asi
    # tambien se detectan commits nuevos tras un force-push que reescribe historia.
    return [sha for sha in todos if sha not in vistos]


# ----------------------------------------------------------------------------
# Exportar un commit a su propia carpeta
# ----------------------------------------------------------------------------
def exportar_commit(sha):
    fecha = git("show", "-s", "--format=%cd", "--date=format:%Y-%m-%d_%H-%M-%S", sha)
    destino = RESPALDOS / f"{fecha}_{sha[:7]}"
    if destino.exists():
        return destino

    git("checkout", "--quiet", "--force", "--detach", sha)
    git("clean", "-fdxq")
    shutil.copytree(CACHE, destino, ignore=shutil.ignore_patterns(".git"))

    # Evidencia: metadatos del commit + huella SHA-256 de cada archivo
    detalle = git("show", "--no-color", "--name-status",
                  "--format=Commit:  %H%nAutor:   %an <%ae>%nFecha:   %ci%nMensaje: %s%n", sha)
    huellas = []
    for archivo in sorted(p for p in destino.rglob("*") if p.is_file()):
        digest = hashlib.sha256(archivo.read_bytes()).hexdigest()
        huellas.append(f"{digest}  {archivo.relative_to(destino).as_posix()}")
    (destino / "_EVIDENCIA_COMMIT.txt").write_text(
        f"Capturado por repo_watcher.py el {ahora()}\n\n{detalle}\n\n"
        "Huellas SHA-256 del contenido exportado:\n" + "\n".join(huellas) + "\n",
        encoding="utf-8",
    )
    solo_lectura(destino)
    return destino


# ----------------------------------------------------------------------------
# Escaneo con expresiones regulares
# ----------------------------------------------------------------------------
def escanear(carpeta, sha):
    """Regresa la lista de hallazgos (nivel, archivo, linea, descripcion)."""
    hallazgos = []
    for archivo in sorted(p for p in carpeta.rglob("*") if p.is_file()):
        relativo = archivo.relative_to(carpeta).as_posix()
        if relativo == "_EVIDENCIA_COMMIT.txt":
            continue

        if PATRON_ARCHIVO_ENV.match(archivo.name) and not PLANTILLAS_ENV.search(archivo.name):
            hallazgos.append(("CRITICO", relativo, 0, "archivo de entorno .env versionado en el repositorio"))

        if archivo.stat().st_size > TAMANO_MAXIMO_ARCHIVO:
            continue
        contenido = archivo.read_bytes()
        if b"\x00" in contenido[:1024]:  # binario
            continue
        texto = contenido.decode("utf-8", errors="ignore")

        # En codigo fuente solo cuentan los literales entre comillas;
        # en archivos de configuracion (.env, .ini, .yml...) tambien KEY=valor.
        es_codigo = archivo.suffix.lower() in EXTENSIONES_CODIGO
        patrones = (PATRON_ASIGNACION_CON_COMILLAS,) if es_codigo else (
            PATRON_ASIGNACION_CON_COMILLAS, PATRON_ASIGNACION_ENV)

        for numero, linea in enumerate(texto.splitlines(), start=1):
            if linea.lstrip().startswith(("#", "//")) and "=" not in linea:
                continue
            for patron in patrones:
                coincidencia = patron.search(linea)
                if not coincidencia:
                    continue
                valor = coincidencia.group("valor").strip()
                if not valor or PATRON_NO_SECRETO.search(valor):
                    break
                hallazgos.append((
                    "ALTO", relativo, numero,
                    f"{coincidencia.group('nombre')} con valor en texto plano: {enmascarar(valor)}",
                ))
                break
            else:
                llave = PATRON_FORMA_DE_LLAVE.search(linea)
                if llave:
                    hallazgos.append(("ALTO", relativo, numero,
                                      f"cadena con forma de llave API: {enmascarar(llave.group(0))}"))
    return hallazgos


def procesar(sha, estado):
    carpeta = exportar_commit(sha)
    mensaje = git("show", "-s", "--format=%s", sha)
    registrar("INFO", f"Commit {sha[:7]} \"{mensaje}\" respaldado en {RESPALDOS.name}/{carpeta.name}")

    hallazgos = escanear(carpeta, sha)
    for nivel, archivo, linea, descripcion in hallazgos:
        ubicacion = f"{archivo}:{linea}" if linea else archivo
        registrar(nivel, f"commit {sha[:7]} | {ubicacion} | {descripcion}")
        estado["archivos_con_hallazgos"].setdefault(archivo, sha)
    if not hallazgos:
        registrar("INFO", f"Commit {sha[:7]}: sin patrones sospechosos.")

    # Un archivo con hallazgos que desaparece NO elimina la exposicion
    cambios = git("show", "--no-color", "--name-status", "--format=", sha).splitlines()
    for cambio in cambios:
        partes = cambio.split("\t")
        if partes[0] == "D" and partes[-1] in estado["archivos_con_hallazgos"]:
            origen = estado["archivos_con_hallazgos"][partes[-1]]
            registrar("AVISO", f"commit {sha[:7]} borra '{partes[-1]}', pero su contenido ya fue "
                               f"capturado del commit {origen[:7]} y sigue en el historial de Git. "
                               "Las credenciales deben ROTARSE.")

    estado["procesados"].append(sha)
    guardar_estado(estado)


# ----------------------------------------------------------------------------
# Bucle principal (polling)
# ----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Bot auditor de commits (laboratorio).")
    parser.add_argument("repo_url", nargs="?", default=REPO_URL_POR_DEFECTO)
    parser.add_argument("--intervalo", type=int, default=INTERVALO_SEGUNDOS)
    parser.add_argument("--una-vez", action="store_true", help="revisa una sola vez y termina")
    args = parser.parse_args()

    RESPALDOS.mkdir(exist_ok=True)
    registrar("INFO", f"Bot iniciado. Repo: {args.repo_url} | rama: {RAMA} | cada {args.intervalo}s")
    preparar_cache(args.repo_url)
    estado = cargar_estado()

    try:
        while True:
            try:
                nuevos = commits_nuevos(estado)
                if nuevos:
                    registrar("INFO", f"{len(nuevos)} commit(s) nuevo(s) detectado(s).")
                for sha in nuevos:
                    procesar(sha, estado)
            except RuntimeError as error:
                registrar("INFO", f"Error temporal, se reintentara: {error}")
            if args.una_vez:
                break
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        registrar("INFO", "Bot detenido por el usuario.")


if __name__ == "__main__":
    sys.exit(main())
