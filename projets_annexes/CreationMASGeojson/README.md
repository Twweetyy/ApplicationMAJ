# CreationMASGeojson : statistiques Insee par IRIS de Roubaix

Ce dossier transforme le classeur `TAB_BDDMAS_Tout_perimetre_<ANNEE>.xlsx`, produit par l'application ApplicationMAJ, en trois fichiers :

| Fichier produit (dans `data/traite/`) | Contenu |
|---|---|
| `stat_insee_iris_<ANNEE>.xlsx` | Table au format `stat_insee_iris2` (champs `champ_insee_N`). Elle contient quatre onglets : l'année, l'historique complet depuis 2016, la source de chaque champ (`mapping_sources`) et les contrôles. |
| `roubaix_iris_<ANNEE>.geojson` | Les 38 polygones IRIS avec les indicateurs, avec des noms de champs `champ_insee_N` à privilégier pour ArcGIS. |
| `roubaix_iris_<ANNEE>_libelles.geojson` | Les mêmes données, mais les champs portent leur libellé lisible (« Population 2016 »…). |

Les colonnes entièrement vides ne sont pas exportées. Les valeurs secrétisées par l'Insee restent vides et ne sont jamais remplacées par 0.

## Organisation du dossier

```
CreationMASGeojson/
├─ README.md
├─ scripts/
│  └─ etl_iris.py                         le script
└─ data/
   ├─ brut/
   │  ├─ Iris_2000.geojson                contours des 38 IRIS (ne change pas)
   │  ├─ stat_insee_iris2.xls             modèle de colonnes + historique 2016-2022 (ne change pas)
   │  └─ TAB_BDDMAS_Tout_perimetre_<ANNEE>.xlsx   à déposer à chaque millésime
   ├─ ref/
   │  ├─ mapping_champs_insee.yml         correspondance champ_insee_N -> colonne du TAB
   │  ├─ variable_population_2006.yml     populations historiques (ne changent pas)
   │  ├─ variable_population_2011.yml
   │  └─ variable_population_2016.yml
   └─ traite/                             sorties du script (une par millésime)
```

## Installation (une seule fois)

```
pip install pandas openpyxl pyyaml xlrd
```

## Mettre à jour avec un nouveau millésime (exemple : 2024)

1. **Générer le TAB 2024** avec ApplicationMAJ à partir des fichiers Insee 2024, puis l'enregistrer sous `data/brut/TAB_BDDMAS_Tout_perimetre_2024.xlsx`.
2. **Laisser la sortie de l'année précédente** (`data/traite/stat_insee_iris_2023.xlsx`) à sa place. Le script y lit l'historique et y ajoute la nouvelle année. Si ce fichier est absent, l'historique s'arrête à 2022, celui du modèle.
3. **Lancer le script** depuis le dossier `CreationMASGeojson` :
   ```
   python scripts/etl_iris.py 2024
   ```
   Sans argument, le script traite 2023.
4. **Contrôler le résultat** :
   - Si le script s'arrête avec un message du type `champ_insee_59: colonne 'Actifs 15-64 ans' introuvable dans l'onglet 'ACT RES'`, c'est que l'Insee a renommé la colonne. Il faut corriger le nom sur cette ligne de `data/ref/mapping_champs_insee.yml`.
   - Si une donnée absente du millésime précédent revient (tranches d'âge, CDD, intérim…), il faut remplacer sa ligne `na: "..."` par `src: [ONGLET, "Nom de colonne"]` dans le même fichier.
   - Dans l'Excel, l'onglet `controles` signale les champs qui varient de plus de 35 % par rapport à l'année précédente, et l'onglet `mapping_sources` donne l'onglet source (donc le millésime) de chaque champ.

Il n'y a rien d'autre à modifier : ni le script, ni `Iris_2000.geojson`, ni les fichiers de population historiques.

## Écrire une ligne du mapping

Dans `data/ref/mapping_champs_insee.yml`, chaque champ se remplit d'une des façons suivantes :

```yaml
champ_insee_2:   {src: [POP, "Population"]}                  # colonne du TAB (onglet sans l'année)
champ_insee_3:   {yml: variable_population_2006.yml}          # valeur lue dans un YAML de data/ref
champ_insee_5:   {expr: "champ_insee_4 / champ_insee_3 * 100"}  # calcul à partir d'autres champs
champ_insee_9:   {na: "raison"}                               # indisponible : colonne vide, non exportée
```

Les accents et les apostrophes typographiques sont ignorés quand le script compare les noms de colonnes.

## Points à connaître

- **Total de population :** il est égal au chiffre communal officiel de l'Insee (98 286 en 2023), grâce à l'arrondi contrôlé d'ApplicationMAJ.
- **Tranches d'âge RP 2023 :** l'Insee a changé le découpage (champs 9 à 13 et 15 : 15-24, 25-39, 40-54, 65-79, 80 ans et plus, part des 65 ans et plus ; nouveau champ 168 : 55-64 ans). Dans l'historique, les années 2016-2022 gardent les anciennes tranches : ne pas comparer ces champs directement avec 2023. L'écart signalé sur champ_insee_13 dans l'onglet `controles` est donc normal.
- **Champs supprimés :** ménages fiscaux (149, 150) et indice de jeunesse (166) sont retirés de toutes les sorties (clé `supprimer:` du mapping).
- **Familles en couple sans enfant (champ 91) :** ce champ vaut couples sans enfant / familles × 100. Il est recalculé sur tout l'historique.
- **Millésimes mélangés :** une « année » regroupe des sources de millésimes différents (par exemple, en 2023 : revenus 2021, CAF et DEFM 2024, CNAM 2025).
- **Publication sur ArcGIS :** utiliser plutôt le GeoJSON `champ_insee_N`, car les libellés contiennent des espaces, des accents et des `%` qu'ArcGIS remplace par des `_`.
