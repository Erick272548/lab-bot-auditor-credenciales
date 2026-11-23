"""
simular_fuga.py - Ejecuta los 3 commits del laboratorio sobre proyecto_ficticio/

  Commit 1: version limpia (os.getenv, .env ignorado)
  Commit 2: fuga accidental (config.py con credenciales + git add -f .env)
  Commit 3: intento de borrado (git rm .env + config.py con os.getenv)

Cada commit se sube con git push a la rama main del repositorio remoto, con una
pausa entre ellos para que el bot (repo_watcher.py, polling cada 15 s) los vea.

Uso:
    python simular_fuga.py https://github.com/USUARIO/REPO.git --pausa 45
    python simular_fuga.py URL --reiniciar      # borra proyecto_ficticio/ y repite

TODAS LAS CREDENCIALES SON FICTICIAS.
"""
import argparse
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
ETAPAS = BASE / "etapas"
PROYECTO = BASE / "proyecto_ficticio"
FIRMA = "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"


def git(*args):
    print(f"  $ git {' '.join(args)}", flush=True)
    subprocess.run(["git", *args], cwd=PROYECTO, check=True)


def copiar(etapa, *nombres):
    origen = ETAPAS / etapa
    for archivo in (origen / n for n in nombres) if nombres else origen.iterdir():
        shutil.copy2(archivo, PROYECTO / archivo.name)


def pausa(segundos, motivo):
    print(f"\n... esperando {segundos}s ({motivo})", flush=True)
    time.sleep(segundos)


def titulo(texto):
    print("\n" + "=" * 70 + f"\n{texto}\n" + "=" * 70, flush=True)


def borrar_carpeta(ruta):
    def quitar_solo_lectura(funcion, camino, _):
        os.chmod(camino, stat.S_IWRITE)
        funcion(camino)
    if sys.version_info >= (3, 12):
        shutil.rmtree(ruta, onexc=quitar_solo_lectura)
    else:
        shutil.rmtree(ruta, onerror=quitar_solo_lectura)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("remoto", help="URL del repositorio publico de prueba")
    parser.add_argument("--pausa", type=int, default=45, help="segundos entre commits")
    parser.add_argument("--reiniciar", action="store_true")
    args = parser.parse_args()

    if PROYECTO.exists():
        if not args.reiniciar:
            raise SystemExit("proyecto_ficticio/ ya existe. Usa --reiniciar para empezar de cero.")
        borrar_carpeta(PROYECTO)
    PROYECTO.mkdir()

    titulo("COMMIT 1 - Version limpia (secretos solo en .env local, ignorado)")
    git("init", "-q", "-b", "main")
    git("config", "user.name", "Dev Ficticio")
    git("config", "user.email", "dev.ficticio@example.com")
    git("remote", "add", "origin", args.remoto)
    copiar("commit1")
    shutil.copy2(ETAPAS / "commit2" / ".env", PROYECTO / ".env")  # .env local del desarrollador
    git("add", ".")
    git("status", "--short", "--ignored")
    git("commit", "-q", "-m", "Estructura base de la API de usuarios" + FIRMA)
    git("push", "-u", "origin", "main")

    pausa(args.pausa, "el bot respalda el commit 1")

    titulo("COMMIT 2 - Fuga accidental (config.py hardcodeado + git add -f .env)")
    copiar("commit2", "config.py")
    git("add", "config.py")
    git("add", "-f", ".env")
    git("status", "--short")
    git("commit", "-q", "-m", "Configurar conexion para la demo" + FIRMA)
    git("push", "origin", "main")

    pausa(args.pausa, "el desarrollador tarda en notar el error; el bot ya lo vio")

    titulo("COMMIT 3 - Intento de borrado (git rm .env + os.getenv)")
    git("rm", "-q", ".env")
    copiar("commit3")
    git("add", "config.py", ".env.example")
    git("status", "--short")
    git("commit", "-q", "-m", "Eliminar .env y mover credenciales a variables de entorno" + FIRMA)
    git("push", "origin", "main")

    titulo("Simulacion terminada. Historial:")
    git("log", "--oneline", "--name-status")


if __name__ == "__main__":
    main()
