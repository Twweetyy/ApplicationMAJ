# Synthèse du projet & Boîte à outils

## `main.py` — Orchestrateur (Pipeline ETL)
Point d'entrée du traitement principal séquentiel :
- Demande le dossier source et ingère les fichiers CSV INSEE.
- Filtre les tables sur la commune de Roubaix (`59512`).
- Nettoie les identifiants, décode les variables INSEE et effectue la jointure du zonage MAS.
- Calcule les indicateurs définis dans `data1/calculated_columns.yml`.
- Exporte le résultat dans `TAB_BDDMAS_INSEE2022_Tout_perimetre.xlsx` et applique la mise en forme finale.

## `fonctions.py` — Moteur de transformation
Contient les fonctions de traitement de données :
- **Ingestion & filtrage :** charge les CSV, associe les millésimes et filtre sur les codes géographiques.
- **Nettoyage :** remplace les codes INSEE (`ns`, `so`) par `NA`, harmonise les décimales et nettoie les colonnes `IRIS`/`CODGEO`.
- **Nomenclature :** décode et renomme les variables via les fichiers YAML thématiques (`LOG`, `POP`, `ACT`, etc.).
- **Calculs :** génère dynamiquement des ratios et pourcentages via `pd.eval` avec gestion des divisions par zéro.
- **Export & styles :** produit le classeur Excel, insère les formules `SUBTOTAL`, applique la charte graphique et intègre l'onglet externe `PETITE ENFANCE 2022`.

## `utils.py` — Référentiels & Fonctions d'appui
Fournit les outils transversaux et gère les fichiers annexes :
- **Chargement des référentiels :** lit les configurations YAML et les zonages MAS (`libelles_iris_roubaix.yml`, `superficies_iris_roubaix.yml`, `Périmètres_MAS.csv`).
- **Jointures :** associe les libellés d'IRIS, les superficies et les périmètres politiques/sociaux aux tables.
- **Helpers :** extrait l'année par regex (`extract_year`), fait correspondre les noms (`get_mapped_name`) et réordonne les colonnes (`insert_position`).

## `traitement_enfants_roubaix.ipynb` — Pipeline Microdonnées & Petite Enfance
Notebook dédié à l'exploitation du fichier détail des individus INSEE (`FD_INDCVI_2022.csv`) :
- **Extraction Dask :** traite volumétriquement les données individus, filtre les moins de 18 ans et cible Roubaix via `iris_roubaix.csv`.
- **Pondération statistique :** somme les poids d'échantillonnage (`IPONDI`) par IRIS et par âge (âge révolu `AGEREV` et âge au millésime `AGED`).
- **Dataviz Seaborn/Matplotlib :** génère les graphiques de distribution d'âge pour toute la ville et exporte automatiquement un graphique par IRIS (38 IRIS).
- **Génération de la table pivot :** crée le tableau croisé IRIS × Âges (0 à 17 ans), y fusionne les zonages `Périmètres_MAS.csv` et ajoute le `TOTAL 0-17`.
- **Production du livrable :** génère et met en forme `tab_mas_age_revolu_enfants_roubaix.xlsx`, qui sert de source directe pour l'onglet réinjecté dans le pipeline principal.

---

## Fonctions recommandées pour un nouveau traitement

### 1. Contrôle qualité & Audit
- **`check_iris_completeness(df, ref_iris_list)`** → **Vérification territoriale** : signale les IRIS manquants ou non conformes avant agrégation.
- **`audit_unmapped_variables(df, mapping_dict)`** → **Contrôle du dictionnaire** : alerte sur les variables présentes dans la source mais absentes du mapping YAML.

### 2. Agrégations & Analyses temporelles
- **`aggregate_by_perimeter(df, group_col, numeric_cols, aggfunc='sum')`** → **Agrégation multi-échelles** : monte les données de l'IRIS vers les quartiers, centres sociaux ou contrats de ville.
- **`calculate_temporal_evolution(df_n, df_n5, key_col, value_cols)`** → **Calcul de variation** : calcule les écarts absolus et relatifs (%) entre deux recensements.

### 3. Automatisation Excel & Mise en page
- **`auto_adjust_column_widths(ws, min_width=12, max_width=50)`** → **Largeurs dynamiques** : adapte chaque colonne à la taille réelle des libellés.
- **`apply_number_formats(ws, format_rules)`** → **Formatage numérique** : applique en masse les séparateurs de milliers, pourcentages et décimales selon le type d'indicateur.
