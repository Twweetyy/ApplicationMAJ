# Nouveau millésime : quoi faire

Ce guide s'adresse à la personne qui met à jour la BDDMAS avec de nouveaux fichiers (Insee, CAF, CNAM, DEFM, RPLS). Dans la plupart des cas, il suffit de déposer les fichiers : le code ne change pas.

## 1. Mise à jour normale

1. **Télécharger les nouveaux fichiers :** Les pages sources sont listées dans `dictionnaires/liens_presentation.yml` et `doc/Fichiers_INSEE_2026.md`. Chaque fichier garde son nom Insee, année comprise (`base-ic-logement-2024.CSV`, `data_CAF2026_Iris.csv`…). CSV ou Parquet, au choix.

2. **Recensement :**
   - Si l'Insee le publie en **cubes au format long** (colonnes `GEO`, `SEX`, `AGE`, `RP_MEASURE`, `OBS_VALUE`…), comme depuis 2023 : placer les 5 cubes dans `data/dataAAAA/sources_brutes_insee/`, nommés `base-ic-pop-AAAA`, `base-ic-log-AAAA`, `base-ic-emp-AAAA`, `base-ic-men-AAAA`, `base-ic-dip-AAAA` (`.csv` ou `.parquet`). Au lancement, `run_portal.bat` les convertit (`scripts/transformer_recensement.py`) et écrit les 5 fichiers à déposer dans `data/dataAAAA/`, avec leurs métas dans `dictionnaires/meta/metaAAAA/`.
   - **Fichiers complémentaires** (facultatifs, mais 10 indicateurs en dépendent) : placer dans `data/dataAAAA/complementaires/`, sous leur nom Insee, les fichiers `DS_RP_POPULATION_COMP`, `DS_RP_EMPLOI_LR_COMP`, `DS_RP_ACTIVITE_PRINC`, `DS_RP_NAVETTES_PRINC`, `DS_RP_MENAGES_COMP`, `DS_RP_FAMILLE_COMP`, `DS_RP_EDUCATION_PRINC`, `DS_RP_LOGEMENT_COMP` (suffixe `_IRIS_AAAA`, `.parquet` ou `.csv`). Le transformer ajoute leurs colonnes aux 5 fichiers produits : CSP, salariés, temps partiel, CDI, lieu de travail, transport, types de ménages et de familles, scolarisation, occupation des logements. Un fichier absent est signalé et ses colonnes ne sont pas produites.
   - Vérifier le **contrôle de cohérence** affiché : Population = Hommes + Femmes, Logements = RP + secondaires + vacants, etc.
   - Si l'Insee le publie **au format large** (une colonne par variable, comme en 2022) : déposer les fichiers directement dans le portail.

3. **Fichier enfants FD_INDCVI :** Le fichier national pèse plusieurs Go ; en extraire Roubaix une fois :

   ```powershell
   python scripts/extraire_indcvi_roubaix.py "chemin\vers\FD_INDCVI_AAAA.csv"
   ```

   La sortie (`data/indcvi_roubaix/FD_INDCVI_AAAA.csv`, quelques Mo) se dépose dans le portail.

4. **Générer le classeur :** Double-cliquer sur `run_portal.bat`, déposer les données (zone A) et leurs `meta_*.csv` (zone B), lire le pré-contrôle (section 2), générer.

5. **Liens de la page Présentation :** Ajouter le lien Insee du nouveau millésime dans `dictionnaires/liens_presentation.yml`, sous le thème concerné (sinon l'ancien lien reste) :

   ```yaml
   POP:
     2023: https://www.insee.fr/fr/statistiques/9054332
     2024: https://www.insee.fr/fr/statistiques/XXXXXXX
   ```

6. **Colonnes renommées ou ajoutées par l'Insee :** Le portail affiche le tableau « Colonnes renommées ou ajoutées automatiquement ». Vérifier chaque ligne « À vérifier ». Pour corriger une décision : dans `dictionnaires/correspondances_auto.yml`, changer `entete` puis mettre `methode: manuel` (l'entrée ne sera plus recalculée).

7. **Une fois le classeur validé**, inscrire le millésime dans `dictionnaires/millesimes_valides.yml` (ex. `POP: '2024'`). Il est alors traité comme une référence, à l'identique, aux prochains lancements.

## 2. Messages du pré-contrôle

| Message | Cause probable | Que faire |
|---|---|---|
| Aucune entrée de files_names.yml ne reconnaît ce nom | Le producteur a renommé son fichier | Ajouter le début du nouveau nom dans `dictionnaires/files_names.yml` (ex. `data_CAF: CAF`). L'année est ignorée. |
| Aucune méta correspondante | Méta non déposée, ou nom différent du fichier de données | Déposer `meta_<nom du fichier>.csv` dans la zone B |
| Plusieurs fichiers du même thème | Deux années d'un même thème dans le lot | N'en garder qu'une |
| IRIS absents ou inconnus | Découpage IRIS modifié, ou fichier incomplet | Vérifier le fichier ; si l'Insee a redécoupé les IRIS, mettre à jour `grand_quartier.yml`, `superficies_iris_roubaix.yml` et `Perimetres_MAS.csv` |
| Colonnes non documentées | Variables absentes de la méta | Sans gravité : elles gardent leur code comme nom |
| Le fichier Périmètres_MAS est requis | Référentiel non déposé | Déposer `Perimetres_MAS.csv` |

**Encadré jaune « indicateurs non calculés »** : une variable utilisée par une formule n'existe pas dans ce millésime (ex. « Pop 60-74 ans » absente du recensement 2023 ; « Salariés 15 ans ou plus » si `DS_RP_ACTIVITE_PRINC` n'a pas été déposé). La colonne reste vide, le reste du classeur est juste. Si la variable existe sous un autre nom, corriger son rattachement (point 6) ou la formule dans `dictionnaires/calculated_columns.yml`.

## 3. Si l'Insee change la structure des cubes

Le transformer s'appuie sur les codes des dimensions des cubes (ex. `AGE = Y_LT2`, `SEX = M`, `RP_MEASURE = DWELLINGS`). S'ils changent :
- le transformer s'arrête avec « Population nulle… les dimensions des cubes ont probablement changé » ;
- ou il signale « [À VÉRIFIER] Colonnes à 0 sur tout Roubaix ».

Ouvrir le cube concerné, relever les nouveaux codes et les reporter dans les filtres de la fonction du thème dans `scripts/transformer_recensement.py` (`transformer_population`, `transformer_logement`…). Relancer avec `--force` et vérifier le contrôle de cohérence.

## 4. IA du module colonnes

Facultative. Configuration dans `.env` (modèle : `.env.exemple`). Au bureau, les appels vers les API d'IA sont bloqués : laisser `BDDMAS_LLM=0`. Sans IA, les colonnes non reconnues apparaissent « À vérifier » et se corrigent une fois dans `correspondances_auto.yml`.

## 5. Base permanente des équipements (BPE)

La BPE se traite à part, dans la page **Équipements BPE** du portail. Pour un nouveau millésime, déposer le fichier BPE et son varmod (`BPE<AA>_anonymisee_varmod.csv`) : les colonnes nouvelles ou absentes sont listées à la fin de la génération. Détails dans le README, section « Classeur des équipements (BPE) ».
