@echo off
rem ------------------------------------------------------------
rem  run_portal.bat – lance le portail BDDMAS via le virtualenv
rem ------------------------------------------------------------

rem Positionner le répertoire courant au même dossier que le script
pushd "%~dp0"

rem Activer l'environnement virtuel
call .venv\Scripts\activate.bat

rem Exécuter le script Python qui démarre le serveur
rem Lancer le serveur en arrière-plan
start "" /B python run_portal.py %*
rem Attendre que le serveur réponde sur le port 5000
powershell -Command "while(-not (Test-NetConnection -ComputerName localhost -Port 5000).TcpTestSucceeded){Start-Sleep -Milliseconds 500}"
rem Ouvrir la page du portail dans le navigateur par défaut
rem start "" "http://127.0.0.1:5000"  # ouvert par le script Python

rem Désactiver l'environnement et revenir au répertoire précédent
call deactivate
popd
