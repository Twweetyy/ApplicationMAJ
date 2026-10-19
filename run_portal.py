#!/usr/bin/env python
"""
run_portal.py – launch the BDDMAS web portal as a standalone Windows executable.

This script mirrors the behaviour of demarrer_portail.ps1:
* verifies required web dependencies (fastapi, uvicorn, multipart),
* picks a free localhost port,
* starts the uvicorn server for webapp:app,
* opens the default browser to the portal URL,
* streams server logs to the console and stops on Ctrl+C.
"""

import sys
import os
import subprocess
import socket
import webbrowser
import importlib.util

def _check_dependency(name: str) -> bool:
    return importlib.util.find_spec(name) is not None

def _ensure_web_stack(python_exe: str) -> None:
    missing = [m for m in ("fastapi", "uvicorn", "multipart") if not _check_dependency(m)]
    if missing:
        print(f"⚠️  Missing web dependencies: {', '.join(missing)}")
        print(f"Install them with: {python_exe} -m pip install -r requirements.txt")
        sys.exit(1)

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def main() -> None:
    python_exe = sys.executable
    _ensure_web_stack(python_exe)
    port = 5000  # port fixe pour être compatible avec le batch
    cwd = os.path.abspath(os.path.dirname(__file__))
    cmd = [python_exe, "-m", "uvicorn", "webapp:app", "--host", "127.0.0.1", "--port", str(port)]
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    print(f"Portail BDDMAS : {url}")
    webbrowser.open(url)
    try:
        for line in proc.stdout:
            sys.stdout.buffer.write(line)
    except KeyboardInterrupt:
        print("\n⚡️  Interruption – stopping server…")
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    main()
