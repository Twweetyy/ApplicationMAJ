# BDDMAS Roubaix – ApplicationMAJ

Application Python de traitement des données infra-communales de Roubaix et de génération du classeur Excel BDDMAS (38 IRIS).

Le projet contient :
- un pipeline (`main_bddmas.py`) utilisable en ligne de commande ou depuis une application ;
- un portail web local (FastAPI / `uvicorn`) pour déposer un lot de fichiers et télécharger le classeur ;
- un convertisseur des cubes Insee du recensement 2023 (`scripts/transformer_2023_roubaix.py`) ;
- un module qui rattache automatiquement les colonnes inconnues d'un nouveau millésime Insee (`modules/colonnes_auto.py`, IA facultative) ;
- des lots d'exemple 2022 et 2023 (`exemples/`) pour essayer le portail tout de suite.

Le pipeline fonctionne avec le recensement 2022 (fichiers Insee au format large) et avec le recensement 2023 (cubes Insee au format long, convertis au préalable).

## Essayer en 2 minutes

1. Installer (voir plus bas), puis double-cliquer sur `run_portal.bat`.
2. Zone **Données** : déposer les fichiers de `exemples/lot2023/data/`.
3. Zone **Métadonnées** : déposer les fichiers de `exemples/lot2023/meta/`.
4. **Analyser le lot**, puis **Exécuter le pipeline ETL**, et télécharger le classeur.

Détails dans `exemples/README.md`.

## Architecture

```text
ApplicationMAJ/
├─ .venv/                          Environnement virtuel (non versionné)
├─ data/                           Fichiers CSV bruts et référentiel des périmètres (ignoré par Git)
│  ├─ data2023/                    CSV 2023 transformés
│  │  └─ sources_brutes_insee/     Cubes Insee 2023 bruts
│  └─ indcvi_roubaix/              FD_INDCVI filtré sur Roubaix
├─ dictionnaires/                  Correspondances de fichiers, variables et onglets (YAML)
│  ├─ millesimes_valides.yml       Dernier millésime validé à la main, par thème
│  ├─ correspondances_auto.yml     Décisions du module colonnes (généré, corrigeable)
│  └─ meta/                        Métadonnées meta_*.csv (dont meta2023/ généré)
├─ modules/
│  ├─ socle_geo.py                 Chargement du référentiel MAS, superficies et jointures
│  ├─ ingestion.py                 Pré-contrôle, lecture, nettoyage et renommage des sources thématiques
│  ├─ indicateurs.py               Calculs dérivés, arrondis et répartitions pondérées des enfants
│  ├─ export_excel.py              Remplissage du modèle et mise en forme Excel
│  ├─ mise_en_page.py              Formats, largeurs, couleurs d'en-têtes, ordre des colonnes
│  ├─ pages_info.py                Pages Présentation et Détail calcul générées selon le lot
│  ├─ colonnes_auto.py             Colonnes inconnues d'un nouveau millésime (sans IA puis IA, cache YAML)
│  ├─ llm_wrapper.py               Appel d'un modèle compatible OpenAI (Groq, Mistral, Ollama…)
│  ├─ export_sig.py                Export des tables attributaires CSV pour les SIG
│  └─ persistence.py               Insertion SQLAlchemy configurable
├─ scripts/
│  ├─ transformer_2023_roubaix.py  Conversion des cubes Insee 2023
│  ├─ extraire_indcvi_roubaix.py   Extraction des lignes Roubaix du FD_INDCVI
│  ├─ simuler_nouveau_millesime.py Faux millésime +1 pour tester colonnes_auto
│  └─ diag.py                      Diagnostic des cubes Insee 2023
├─ exemples/                       Lots 2022 et 2023 prêts à déposer dans le portail
├─ web/                            Front du portail (index.html, multi-upload.js, styles.css)
├─ exports_sig/                    Exportations SIG (ignoré par Git)
├─ main_bddmas.py                  Orchestrateur du pipeline
├─ webapp.py                       API FastAPI du portail
├─ run_portal.bat                  Lanceur du portail (double-clic)
├─ run_portal.py                   Démarrage du serveur Uvicorn
├─ .env.example                    Modèle de configuration de l'IA (copier en .env)
├─ TAB_BDDMAS_INSEE2022_MODELE.xlsx  Classeur modèle conservé comme gabarit
├─ requirements.txt                Dépendances Python
└─ README.md                       Vous êtes ici
```

## Installation

Prérequis : Python 3.11 ou plus récent. Depuis le dossier du projet :

```powershell
python -m pip install -r requirements.txt
```

Optionnel (IA du module colonnes) : copier `.env.example` en `.env` et renseigner la clé. Sans `.env`, ou avec `BDDMAS_LLM=0`, le pipeline fonctionne sans IA.

## Lancement

### Portail web (usage courant)

```bat
run_portal.bat
```
- Le script active le virtualenv (`.venv`).
- Il lance `run_portal.py`, qui démarre le serveur Uvicorn sur `http://127.0.0.1:5000`.
- Le navigateur s'ouvre automatiquement sur l'URL du portail.
- Pour arrêter le serveur, appuyez sur `Ctrl+C`.
- Le message « Les chemins d'accès UNC ne sont pas pris en charge » au démarrage est sans conséquence.
- Après une modification du code, fermez l'ancien serveur avant de relancer, puis faites `Ctrl+F5` dans le navigateur.

Lancement manuel équivalent :

```powershell
python -m uvicorn webapp:app --host 127.0.0.1 --port 8000
```
puis ouvrir `http://127.0.0.1:8000`.

L'interface affiche le pré-contrôle avant d'autoriser la génération. Les jobs sont isolés dans le répertoire temporaire du système (`%TEMP%\bddmas-web-jobs`) et nettoyés après 12 heures. Les exports SIG et SQL ne sont pas produits par l'interface.

### Pipeline en ligne de commande

```powershell
python main_bddmas.py
```
Les sources sont lues dans `data/` et les métadonnées dans `dictionnaires/meta/`. Le classeur `TAB_BDDMAS_INSEE2022_Tout_perimetre.xlsx` est généré à la racine à partir de `TAB_BDDMAS_INSEE2022_MODELE.xlsx`. Le modèle d'origine n'est pas modifié. Les exports SIG et l'insertion SQL sont produits en plus (voir plus bas).

Pendant l'exécution, `tqdm` affiche la progression des étapes du pipeline, la lecture du recensement et l'écriture des lignes Excel. Pour le recensement, le nombre de lignes et le temps restant sont estimés à partir des 2 premiers Mo du fichier ; cette estimation est indicative.

## Constituer un lot (portail)

**Zone A – Données**
- `Perimetres_MAS.csv` (obligatoire)
- Recensement : `base-ic-evol-struct-pop-AAAA.CSV`, `base-ic-activite-residents-AAAA.CSV`, `base-ic-couples-familles-menages-AAAA.CSV`, `base-ic-diplomes-formation-AAAA.CSV`, `base-ic-logement-AAAA.CSV`
- Filosofi : `BASE_TD_FILO_IRIS_AAAA_DEC.csv`, `BASE_TD_FILO_IRIS_AAAA_DISP.csv`
- `data_CAF…`, `data_CNAM…`, `data_DEFM…`, `data_RPLS…`
- `FD_INDCVI_AAAA.csv` (version filtrée Roubaix, voir plus bas)

**Zone B – Métadonnées**
- Un `meta_<nom du fichier>.csv` par fichier de données, et `varmod_indcvi_AAAA.csv`.
- Obligatoire : le portail n'utilise pas le dossier `dictionnaires/meta` du disque.

**Règles**
- Un seul fichier par thème dans un lot (ex. pas de POP 2022 et POP 2023 ensemble : erreur bloquante `versions_multiples_theme`).
- Les années peuvent différer d'un thème à l'autre (recensement 2023 + Filosofi 2021 + CAF 2024…).
- Le classeur ne contient que ce qui est déposé : un onglet sans fichier dans le lot reste vide.

## Fichiers d'entrée

- `Perimetres_MAS.csv` est le référentiel géographique requis. Il doit contenir au minimum `IRIS` et les colonnes de périmètre utilisées par `modules/socle_geo.py`.
- Les CSV thématiques Insee, FILO, CAF, CNAM, DEFM et RPLS : le nom du fichier doit correspondre à une entrée de `dictionnaires/files_names.yml` ; les fichiers non mappés sont signalés par le pré-contrôle.
- Les métadonnées `meta_*.csv` sont appariées par nom normalisé (année ignorée). Les colonnes `COD_VAR` et `LIB_VAR` fournissent les libellés ; les modalités textuelles sont traduites à partir de `COD_MOD` et `LIB_MOD` lorsqu'elles existent. Les dictionnaires YAML restent utilisés en complément ou en repli.
- Le fichier individuel du recensement commence par `FD_INDCVI_` et doit contenir `IRIS`, `AGEREV`, `AGED` et `IPONDI`. La méta `varmod_indcvi_AAAA.csv` documente ces champs. Seules les colonnes requises sont lues, par blocs.
- `dictionnaires/superficies_iris_roubaix.yml` fournit les superficies par code IRIS, utilisées pour les densités et superficies calculées.
  
## Recensement 2023 : préparation des données

Les fichiers Insee 2023 sont des cubes au format long (`GEO`, `SEX`, `AGE`, `RP_MEASURE`, `OBS_VALUE`…). Ils doivent être convertis avant d'être utilisés.

1. Placer les cubes bruts dans `data/data2023/sources_brutes_insee/` : `base-ic-pop-2023.csv`, `base-ic-log-2023.csv`, `base-ic-emp-2023.csv`, `base-ic-men-2023.csv`, `base-ic-dip-2023.csv`.
2. Lancer :
   ```powershell
   python scripts/transformer_2023_roubaix.py
   ```
3. Le script écrit les 5 CSV au format large dans `data/data2023/` (`base-ic-evol-struct-pop-2023.CSV`, etc.) et leurs métadonnées dans `dictionnaires/meta/meta2023/`.
4. Vérifier le bloc « Contrôle de cohérence » affiché en fin d'exécution : Population = Hommes + Femmes, Logements = RP + résidences secondaires + vacants, etc.

Points clés du transformer :
- `valeur_cube` ramène à `_T` toute dimension non citée dans un filtre, pour éviter le double comptage.
- Chaque thème fixe sa mesure (`RP_MEASURE`) : `DWELLINGS` pour le logement, `POP` pour les autres.
- Le nombre de ménages (COU FAM) est repris des résidences principales du cube logement, le cube ménages n'ayant pas de mesure « ménages ».
- Pas de tranche 25-29 ans dans le cube 2023 : `Pop 15-29 ans` est remplacée par `Pop 15-24 ans`.

Ne plus utiliser `adapt_2023_transform.py` (renommé en `.bak`) : il écrivait les cubes bruts sous les mêmes noms et écrasait les fichiers transformés.

## Fichier enfants FD_INDCVI (portail)

Le fichier national (~4 Go) sature le disque C: lors de l'envoi au portail, qui le copie dans `%TEMP%`. Il faut en extraire une fois les lignes de Roubaix :

```powershell
python scripts/extraire_indcvi_roubaix.py
```
- Renseigner le chemin du fichier national dans la variable `SOURCE` du script.
- Sortie : `data/indcvi_roubaix/FD_INDCVI_AAAA.csv` (quelques Mo), même nom et mêmes colonnes que l'original. Aucune modification du pipeline n'est nécessaire.
- En cas d'erreur `No space left on device`, vider `%TEMP%\bddmas-web-jobs`.

## Dictionnaires

- `files_names.yml` : motif de nom de fichier → thème, au format `motif: THÈME` (ex. `base-ic-evol-struct-pop: POP`). L'année est ignorée lors de la comparaison : une même entrée sert pour 2022 et 2023.
- `calculated_columns.yml` : indicateurs calculés. Les références à `POP 2022`, `ACT RES 2022`… sont résolues automatiquement vers l'année présente dans le lot (`modules/indicateurs.py`, `_resoudre_table`).
- `info_pages.yml` : titres des onglets Excel.
- `dictionnaire_variables*.yml` : libellés de repli des variables.

## Étapes du pipeline

Avant les étapes ci-dessous, `analyser_fichiers_entree` vérifie les sources, les métadonnées, les clés géographiques et les doublons de millésime. Le résultat structuré est disponible pour une interface ; les erreurs bloquantes arrêtent le pipeline avant les calculs.

1. `modules/ingestion.py` identifie les CSV thématiques mappés, les nettoie, filtre Roubaix lorsque la source possède une colonne `IRIS` ou `COM`, puis traduit les variables. Chaque table est nommée `THÈME ANNÉE` (ex. `POP 2023`), l'année étant lue dans le nom du fichier.
2. Le recensement enfants est lu par blocs. `modules/indicateurs.py` filtre les codes IRIS commençant par `59512`, sélectionne les âges inférieurs à 18 ans et additionne le poids `IPONDI` par IRIS et par âge.
3. Deux répartitions sont produites : âge révolu (`AGEREV`) et âge au millésime (`AGED`). Elles alimentent les onglets `PETITE ENFANCE {année du FD_INDCVI}` et `PETITE ENFANCE MILLÉSIME`, avec les colonnes `Age : 0` à `Age : 17`. Les effectifs sont des estimations pondérées de l'échantillon du recensement. La colonne `Crèches` du modèle reste vide tant qu'aucune source de crèches n'est configurée.
4. `modules/socle_geo.py` rattache le référentiel `Perimetres_MAS.csv` et les superficies par IRIS. Les indicateurs configurés dans `calculated_columns.yml` sont ensuite calculés.
5. `modules/indicateurs.py` applique les règles de `r_gles_d_arrondis_compl_tes.md` à toutes les colonnes : volumes à l'entier le plus proche (les demis vers le haut), parts/taux à 1 décimale, indices/densités/moyennes/superficies à 2 décimales, variables RPLS `TX…` et `…LOY` à 2 décimales. Les identifiants et libellés restent textuels ; toute autre colonne numérique est arrondie à l'entier.
6. `modules/export_excel.py` remplit les onglets du classeur modèle en conservant leurs en-têtes et leur mise en forme, et écrit les formules de sous-totaux adaptées au nombre de lignes. Les onglets de données du modèle sont vidés avant écriture. Les colonnes du modèle absentes du lot sont supprimées sans laisser de colonnes vides ; les variables nouvelles sont insérées avant `Superficie en km²`, avec le style des colonnes de données.
7. `modules/export_sig.py` crée un CSV par thème dans `exports_sig/`, avec `IRIS` en première colonne sur 9 caractères. Ces exports contiennent des attributs à joindre aux couches IRIS existantes, sans géométrie. (Ligne de commande uniquement.)
8. `modules/persistence.py` insère les tables dans la base configurée uniquement si `BDDMAS_DATABASE_URL` est définie. (Ligne de commande uniquement.)

## Nouveau millésime : colonnes inconnues

Quand l'Insee renomme ou ajoute des variables (fichiers 2024, 2025…), `modules/colonnes_auto.py` décide seul où les placer dans le classeur, sans intervention manuelle.

- **Quand** : seulement pour un fichier plus récent que le millésime validé de son thème (`dictionnaires/millesimes_valides.yml`). Les lots 2022 et 2023, vérifiés à la main, ne sont jamais modifiés.
- **Comment**, dans l'ordre : correspondance exacte, cache des décisions passées, correspondance approchée (libellés quasi identiques), puis IA si elle est configurée. Une décision peu sûre laisse la colonne sous son libellé source, marquée « non résolue ».
- **Où voir** : tableau « Colonnes auto » dans le portail après génération, et avertissement dans le rapport.
- **Corriger** : dans `dictionnaires/correspondances_auto.yml`, changer `entete` puis mettre `methode: manuel`. L'entrée ne sera plus jamais recalculée.
- **Tester** : `python scripts/simuler_nouveau_millesime.py --lot <dossier du lot 2023>` fabrique un faux lot 2024 (codes renommés, libellés reformulés) et écrit le classeur et `decisions.json` dans `sorties/simulation/`, sans toucher au dépôt.

Configuration de l'IA (`.env`, jamais versionné) : `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` (tout fournisseur compatible OpenAI : Groq, Mistral, Gemini, Ollama en local), `BDDMAS_LLM` (0 pour désactiver), `BDDMAS_LLM_CONFIANCE_MIN` (0,8 par défaut).

## Utilisation depuis une application

Le traitement est exposé par `executer_pipeline`. Une application peut fournir un dossier de dépôt et un chemin de résultat sans modifier les constantes du lanceur local :

```python
from main_bddmas import ErreurPrecontrole, executer_pipeline

try:
    resultat = executer_pipeline(
        dossier_data="job/data",
        dossier_dicos="dictionnaires",
        chemin_sortie="job/TAB_BDDMAS_Tout_perimetre.xlsx",
        chemin_modele="TAB_BDDMAS_INSEE2022_MODELE.xlsx",
        dossier_export_sig=None,
        persister_sql=False,
        afficher_progression=False,
    )
except ErreurPrecontrole as erreur:
    rapport = erreur.rapport
```

Le rapport de pré-contrôle est également renvoyé dans `resultat["precontrole"]`. `dossier_export_sig=None` et `persister_sql=False` désactivent ces sorties, ce qui convient à une génération web isolée. Le périmètre est fourni dans `dossier_data` ; les chemins du modèle, des superficies, des calculs et des titres peuvent être surchargés si besoin.

## Base de données

Définir `BDDMAS_DATABASE_URL` dans l'environnement avant de lancer le pipeline. La valeur doit être une URL SQLAlchemy pointant vers la base cible `bddmas` ; ne pas inscrire d'identifiants dans les fichiers du projet. Le pilote adapté au moteur de base choisi doit également être installé.

Par défaut, `BDDMAS_IF_EXISTS=fail` empêche de remplacer ou de compléter une table déjà existante. Les modes `append` et `replace` sont disponibles en définissant explicitement cette variable. `append` peut créer des doublons lors d'exécutions successives ; `replace` remplace les tables concernées.

Exemple de test local avec SQLite :

```powershell
$env:BDDMAS_DATABASE_URL = "sqlite:///bddmas.sqlite"
python main_bddmas.py
```

Si `BDDMAS_DATABASE_URL` n'est pas définie, l'insertion SQL est ignorée et les sorties Excel/SIG sont tout de même générées.

## Limites connues

Avertissements attendus avec le recensement 2023 (variables absentes des cubes Insee 2023) :
- Salariés, CDI / fonction publique, travail dans la commune de résidence (ACT RES) ;
- Familles, familles monoparentales, couples avec enfants, familles nombreuses (COU FAM) ;
- Pop 60-74 ans et indicateurs dérivés (POP).

Les indicateurs concernés restent vides ; le reste du classeur est calculé.

Depuis le poste de la mairie, les appels HTTPS vers les API d'IA sont bloqués : y laisser `BDDMAS_LLM=0`. Le module colonnes fonctionne alors sans IA (les colonnes non reconnues sont à corriger une fois dans `correspondances_auto.yml`).

## Gestion du dépôt Git

- Les dossiers `build/`, `dist/`, `*.spec`, `*.exe` et les caches Python sont ignorés via `.gitignore`.
- Les dossiers de données (`data/`, `exports_sig/`) sont également exclus.
- Un hook `pre-commit` empêche d'ajouter accidentellement des fichiers volumineux (plus de 5 Mo) ou les dossiers de données. `exemples/*/data/` est ré-autorisé dans `.gitignore` ; pour un fichier d'exemple plus lourd, commit avec `git commit --no-verify`.
- `.env` (clés API) n'est jamais versionné.

## Créer une release

Après chaque version stable, créez une **release** GitHub (ex. `v1.0`) et ajoutez le fichier `run_portal.bat` en tant qu'actif.

---
*Ce README a été rédigé en français conformément à la convention de messages de commit du projet.*