#!/usr/bin/env python
"""
run_portal.py – lance le portail web BDDMAS.

Ce script :
* verifie les dependances web requises (fastapi, uvicorn, multipart),
* demarre le serveur uvicorn pour webapp:app sur le port 5000,
* attend que le serveur soit reellement pret avant d'ouvrir le navigateur,
* redirige les logs en direct dans la console et s'arrete proprement avec Ctrl+C.
"""

import sys
import os
import subprocess
import webbrowser
import importlib.util
import time
import urllib.request


def _check_dependency(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _ensure_web_stack(python_exe: str) -> None:
    missing = [m for m in ("fastapi", "uvicorn", "multipart") if not _check_dependency(m)]
    if missing:
        print(f"⚠️  Dependances web manquantes : {', '.join(missing)}")
        print(f"Installez-les avec : {python_exe} -m pip install -r requirements.txt")
        sys.exit(1)


def main() -> None:
    python_exe = sys.executable
    _ensure_web_stack(python_exe)
    port = 5000
    cwd = os.path.abspath(os.path.dirname(__file__))
    cmd = [python_exe, "-m", "uvicorn", "webapp:app", "--host", "127.0.0.1", "--port", str(port)]
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    print(f"Demarrage du portail BDDMAS sur {url}...")

    # Attendre que le serveur soit pret avant d'ouvrir le navigateur
    deadline = time.time() + 30
    server_ready = False
    while time.time() < deadline:
        if proc.poll() is not None:
            print("⚠️  Le serveur Uvicorn s'est arrete prematurement.")
            break
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    server_ready = True
                    break
        except Exception:
            time.sleep(0.5)

    if server_ready:
        print(f"Serveur pret. Ouverture du navigateur sur {url}")
        webbrowser.open(url)
    elif proc.poll() is None:
        print("⚠️  Le serveur n'a pas repondu apres 30 s d'attente.")

    try:
        for line in proc.stdout:
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
    except KeyboardInterrupt:
        print("\n⚡️  Interruption – arret du serveur en cours...")
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()
