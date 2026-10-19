# ApplicationMAJ

## Description
Ce projet contient le portail BDDMAS, un serveur FastAPI lancé via `uvicorn`. Le lancement du portail se fait désormais à l'aide d'un script batch simple qui active l'environnement virtuel et démarre le serveur.

## Lancement du portail
```bat
run_portal.bat
```
- Le script active le virtualenv (`.venv`).
- Il lance `run_portal.py` qui démarre le serveur Uvicorn sur un port libre.
- Le navigateur s'ouvre automatiquement sur l'URL du portail.
- Pour arrêter le serveur, appuyez sur `Ctrl+C`.

## Structure du dépôt
```
ApplicationMAJ/
├─ .venv/                # Environnement virtuel (non versionné)
├─ data/                 # Données volumineuses (ignorées)
├─ exports_sig/          # Exportations (ignorées)
├─ run_portal.bat       # Lanceur batch (à double‑clic)
├─ run_portal.py        # Script Python qui démarre le serveur
├─ requirements.txt      # Dépendances du projet
└─ README.md             # Vous êtes ici
```

## Gestion du dépôt Git
- Les dossiers `build/`, `dist/`, `*.spec`, `*.exe` et les caches Python sont ignorés via `.gitignore`.
- Les dossiers de données (`data/`, `exports_sig/`) sont également exclus.
- Un hook `pre‑commit` empêche d'ajouter accidentellement des fichiers volumineux ou les dossiers de données.

## Créer une release
Après chaque version stable, créez une **release** GitHub (ex. `v1.0`) et ajoutez le fichier `run_portal.bat` en tant qu’actif.

---
*Ce README a été rédigé en français conformément à la convention de messages de commit du projet.*