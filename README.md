# BDDMAS Roubaix

Application Python de traitement des données infra-communales de Roubaix et de génération du classeur Excel BDDMAS.

## Architecture

```text
data/                   Fichiers CSV bruts et référentiel des périmètres
dictionnaires/          Correspondances de fichiers, variables et onglets (YAML)
modules/
	socle_geo.py          Chargement du référentiel MAS, superficies et jointures
	ingestion.py         Lecture, nettoyage et renommage des sources thématiques
	indicateurs.py        Calculs dérivés et répartitions pondérées des enfants
	export_excel.py       Remplissage du modèle et mise en forme Excel
	export_sig.py         Export des tables attributaires CSV pour les SIG
	persistence.py        Insertion SQLAlchemy configurable
main_bddmas.py          Orchestrateur du pipeline
TAB_BDDMAS_INSEE2022_MODELE.xlsx  Classeur modèle conservé comme gabarit
requirements.txt        Dépendances Python
```

## Installation et lancement

Prérequis : Python 3.11 ou plus récent. Depuis le dossier du projet, installer les dépendances et lancer l'orchestrateur :

```powershell
python -m pip install -r requirements.txt
python main_bddmas.py
```

Le classeur `TAB_BDDMAS_INSEE2022_Tout_perimetre.xlsx` est généré à la racine à partir de `TAB_BDDMAS_INSEE2022_MODELE.xlsx`. Le modèle d'origine n'est pas modifié. Les onglets de données du modèle sont vidés avant d'y écrire les sources présentes, afin que les anciennes lignes d'exemple ne soient pas prises pour des résultats.

Pendant l'exécution, `tqdm` affiche la progression des étapes du pipeline, la lecture du recensement et l'écriture des lignes Excel. Pour le recensement, le nombre de lignes et le temps restant sont estimés à partir des 2 premiers Mo du fichier; cette estimation est indicative et s'affine au fur et à mesure de la lecture.

## Fichiers d'entrée

- `data/Périmètres_MAS.csv` est le référentiel géographique requis. Il doit contenir au minimum `IRIS` et les colonnes de périmètre utilisées par `modules/socle_geo.py`.
- Les CSV thématiques INSEE, CAF, CNAM, DEFM et RPLS sont déposés dans `data/`. Le nom du fichier doit correspondre à une entrée de `dictionnaires/files_names.yml`; les fichiers non mappés et les fichiers `meta_` sont ignorés. Les noms de variables sont traduits avec le dictionnaire thématique correspondant.
- Les sources thématiques actuellement présentes sont POP 2022 et LOG 2022. Les onglets des autres thèmes restent dans le modèle mais ne sont pas alimentés tant que leurs sources correspondantes ne sont pas déposées dans `data/`.
- `data/FD_INDCVI_2022.csv` est la source individuelle du recensement (plusieurs Go). Elle doit être séparée par des points-virgules et contenir `IRIS`, `AGEREV`, `AGED` et `IPONDI`. Seules ces colonnes sont lues, par blocs.
- `dictionnaires/superficies_iris_roubaix.yml` fournit les superficies par code IRIS, utilisées pour les densités et superficies calculées.

## Étapes du pipeline

1. `modules/ingestion.py` identifie d'abord les seuls CSV thématiques mappés, les nettoie, filtre Roubaix lorsque la source possède une colonne `IRIS` ou `COM`, puis traduit les variables.
2. Le recensement enfants est lu par blocs. `modules/indicateurs.py` filtre les codes IRIS commençant par `59512`, sélectionne les âges inférieurs à 18 ans et additionne le poids `IPONDI` par IRIS et par âge.
3. Deux répartitions sont produites : âge révolu (`AGEREV`) et âge au millésime (`AGED`). Elles alimentent les onglets `PETITE ENFANCE 2022` et `PETITE ENFANCE MILLÉSIME`, avec les colonnes `Age : 0` à `Age : 17`. Les effectifs sont des estimations pondérées de l'échantillon du recensement. La colonne `Crèches` du modèle reste vide tant qu'aucune source de crèches n'est configurée.
4. `modules/socle_geo.py` rattache le référentiel `Périmètres_MAS.csv` et les superficies par IRIS. Les indicateurs configurés dans `dictionnaires/calculated_columns.yml` sont ensuite calculés.
5. Avant les sorties, `modules/indicateurs.py` applique les règles de `r_gles_d_arrondis_compl_tes.md` à toutes les colonnes actuelles et futures : volumes numériques à l'entier le plus proche (les demi vers le haut), parts/taux à 1 décimale, indices/densités/moyennes/superficies à 2 décimales, variables RPLS `TX…` et `…LOY` à 2 décimales. Les identifiants et libellés restent textuels; toute autre colonne numérique est traitée comme un dénombrement et arrondie à l'entier.
6. `modules/export_excel.py` remplit les onglets du classeur modèle en conservant leurs en-têtes et leur mise en forme. Il écrit également les formules de sous-totaux adaptées au nombre de lignes.
7. `modules/export_sig.py` crée un CSV par thème dans `exports_sig/`, avec `IRIS` en première colonne et codé sur 9 caractères. Ces exports contiennent des attributs à joindre aux couches IRIS existantes; ils ne contiennent pas de géométrie.
8. `modules/persistence.py` insère les tables dans la base configurée uniquement si `BDDMAS_DATABASE_URL` est définie.

## Base de données

Définir `BDDMAS_DATABASE_URL` dans l'environnement avant de lancer le pipeline. La valeur doit être une URL SQLAlchemy pointant vers la base cible `bddmas`; ne pas inscrire d'identifiants dans les fichiers du projet. Le pilote adapté au moteur de base choisi doit également être installé.

Par défaut, `BDDMAS_IF_EXISTS=fail` empêche de remplacer ou de compléter une table déjà existante. Les modes `append` et `replace` sont disponibles en définissant explicitement cette variable. `append` peut créer des doublons lors d'exécutions successives; `replace` remplace les tables concernées.

Exemple de test local avec SQLite :

```powershell
$env:BDDMAS_DATABASE_URL = "sqlite:///bddmas.sqlite"
python main_bddmas.py
```

Si `BDDMAS_DATABASE_URL` n'est pas définie, l'insertion SQL est ignorée et les sorties Excel/SIG sont tout de même générées. Les titres Excel sont configurés dans `dictionnaires/info_pages.yml`.