@echo off
rem ------------------------------------------------------------
rem  run_portal.bat – lance le portail BDDMAS via le virtualenv
rem ------------------------------------------------------------

rem Positionner le répertoire courant au même dossier que le script
pushd "%~dp0"

rem Activer l'environnement virtuel
call .venv\Scripts\activate.bat

rem Exécuter le script Python qui démarre le serveur
python run_portal.py %*

rem Désactiver l'environnement et revenir au répertoire précédent
call deactivate
popd
