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

rem Transformer les cubes bruts Insee 2023 s'il y en a
set "BRUT=data\data2023\sources_brutes_insee"
if exist "%BRUT%\base-ic-*-2023.csv" (
    echo ============================================================
    echo  Transformation recensement 2023 - Roubaix
    echo ============================================================
    python scripts\transformer_2023_roubaix.py
    if errorlevel 1 (
        echo.
        echo [ATTENTION] Le transformer a echoue, le portail demarre quand meme.
        pause
    )
    echo.
) else (
    echo [INFO] Aucun cube brut 2023 dans %BRUT%, transformation ignoree.
    echo.
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