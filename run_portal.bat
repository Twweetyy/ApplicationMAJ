@echo off
rem ------------------------------------------------------------
rem  run_portal.bat - transforme les cubes Insee 2023 puis lance
rem  le portail BDDMAS via le virtualenv
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

rem Transformer les cubes bruts Insee du recensement (data\dataAAAA\sources_brutes_insee),
rem quel que soit le millesime ; le script ne fait rien s'il n'y a pas de cube ou s'il est a jour
echo ============================================================
echo  Transformation recensement - Roubaix
echo ============================================================
python scripts\transformer_recensement.py
if errorlevel 1 (
    echo.
    echo [ATTENTION] Le transformer a echoue, le portail demarre quand meme.
    pause
)
echo.

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