@echo off
rem ------------------------------------------------------------
rem  run_portal.bat – lance le portail BDDMAS via le virtualenv
rem ------------------------------------------------------------

rem Positionner le repertoire courant au meme dossier que le script
pushd "%~dp0"

rem Activer l'environnement virtuel
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [ERREUR] L'environnement virtuel .venv est introuvable.
    pause
    popd
    exit /b 1
)

rem Lancer le superviseur Python en premier plan (il gere l'attente du serveur,
rem l'ouverture unique du navigateur, l'affichage des logs et l'arret propre).
python run_portal.py %*

if errorlevel 1 (
    echo.
    echo [ERREUR] Le serveur s'est arrete avec une erreur.
    pause
)

rem Desactiver l'environnement et revenir au repertoire precedent
call deactivate
popd
