# DIRECTIVES D'ARRONDIS : DONNÉES INSEE & INDICATEURS CALCULÉS

**Objectif :** Fournir à l'IA ou au développeur un arbre de décision exhaustif pour déterminer le type d'arrondi à appliquer aux variables issues des fichiers bruts Insee (POP, RPLS, ACT, COU, DEFM, DIP, LOG) ainsi qu'aux indicateurs recalculés en post-traitement (calculated_columns.yml).

---

## PARTIE 1 : DONNÉES BRUTES DE L'INSEE

### CATÉGORIE 1 : Nombres Entiers (0 décimale)
**Règle technique :** Arrondir à l'entier le plus proche (ex: `round(0).astype("Int64")`).
**Raison sémantique :** Ces variables représentent des entités physiques et indivisibles (personnes, ménages, logements). Même si les algorithmes de l'INSEE génèrent des décimales via des pondérations, la restitution doit se faire en entiers.
**Arrondi contrôlé :** pour les effectifs additifs (ceux qui ont un total dans le classeur), l'arrondi se fait par la méthode du plus fort reste (`_arrondi_controle` dans `modules/indicateurs.py`) : la somme des IRIS arrondis égale l'arrondi de la somme exacte, donc le chiffre communal officiel (ex. 98 286 habitants en 2023 au lieu de 98 284 avec un arrondi IRIS par IRIS). Chaque IRIS reste à ±1 de sa valeur exacte.
**Variables concernées :**
*   **POP (Population) :** Toutes les variables (`POP`, `POP0002`, `H1529`, `FR`, etc.)
*   **ACT (Activité) :** Toutes les variables (`ACT1564`, `CHOM1524`, `INACT1564`, etc.)
*   **COU (Couples / Familles) :** Toutes les variables (`MEN`, `FAM`, `PMENFAM`, etc.)
*   **DEFM (Demandeurs d'emploi) :** Toutes les variables (`ABCDE`, `ABC_H`, `ABC_DUR1`, etc.)
*   **DIP (Diplômes) :** Toutes les variables (`SCOL0205`, `DIPLMIN`, `BAC`, etc.)
*   **LOG (Logements) :** Variables quantifiant des logements/ménages/pièces (`LOG`, `RP`, `PROP`, `VOIT1`, etc.)
*   **RPLS (Parc Social) :** Variables de décompte de logements (`NBLSPLS`, `NBLSMES`).

### CATÉGORIE 2 : Taux et Proportions (1 ou 2 décimales)
**Règle technique :** Conserver 1 ou 2 décimales.
**Raison sémantique :** Ce sont des pourcentages continus, arrondir à l'entier ferait perdre de la nuance.
**Variables concernées :**
*   **RPLS :** Préfixes `TX` (ex: `TXVAC`, `TXROT`, `TXLS3P`, etc.)

### CATÉGORIE 3 : Valeurs Monétaires et Moyennes (2 décimales)
**Règle technique :** Conserver 2 décimales.
**Raison sémantique :** Ce sont des valeurs financières (Loyer par mètre carré). L'usage veut qu'on conserve les centimes.
**Variables concernées :**
*   **RPLS :** Suffixe `LOY` (ex: `MOYLOY`, `Q1LOY`, `MEDLOY`).

### CATÉGORIE 4 : Variables Ignorées (Pas d'arrondi, Format Texte)
**Règle technique :** Convertir en chaîne de caractères (`String`). 
**Raison sémantique :** Identifiants géographiques ou libellés textuels ne devant pas être "parsés" en numérique.
**Variables concernées :**
*   `COM`, `COM 1`, `CODGEO`, `TYP_IRIS`, `LAB_IRIS`, `LIBIRIS`, `NOTE`.

---

## PARTIE 2 : INDICATEURS CALCULÉS EN POST-TRAITEMENT

### RÈGLE A : Les Volumes et Sommes (0 décimale)
**Règle technique :** Arrondir à l'entier le plus proche (ex: `round(0).astype("Int64")`).
**Raison sémantique :** Les additions/soustractions d'unités physiques restent des unités physiques.
**Détection via nom de colonne :** `Nombre de...`, `Population...`, `Ménages...`
**Exemples :** `Population (ACT RES)`, `Nombre de familles nombreuses`, `Ménages emménagés moins 10 ans`.

### RÈGLE B : Les Parts et Taux (% -> 1 décimale)
**Règle technique :** Conserver 1 décimale.
**Raison sémantique :** Exprime un ratio sur 100. L'usage statistique standard pour la restitution grand public est de 1 décimale.
**Détection via nom de colonne :** Commence par `Part...`, `Taux...` ou contient `(%)`.
**Exemples :** `Part de la population en âge de travailler (%)`, `Taux d’emploi des 15-64 ans (%)`, `Part des ménages avec famille(s) (%)`.

### RÈGLE C : Indices, Densités et Moyennes (1 à 2 décimales)
**Règle technique :** Conserver 1 à 2 décimales.
**Raison sémantique :** Ratios entre unités hétérogènes (hab/km²) ou indices socio-démographiques.
**Détection via nom de colonne :** Commence par `Densité...`, `Indice...`, `Taille...`, `Superficie...`
**Exemples :** `Densité de population en hab/km²`, `Indice de jeunesse`, `Taille moyenne des ménages`.

---

## 💻 IMPLÉMENTATION PYTHON (Pandas)
Voici le script consolidé permettant à une IA d'automatiser le typage et l'arrondi de toutes les colonnes d'un DataFrame de manière dynamique :

```python
import pandas as pd

# 1. Variables textuelles à exclure du traitement numérique
colonnes_texte = ['COM', 'COM 1', 'CODGEO', 'TYP_IRIS', 'LAB_IRIS', 'LIBIRIS', 'NOTE']

for col in df.columns:
    # --- CATÉGORIE 4 : Métadonnées et Texte ---
    if col in colonnes_texte:
        df[col] = df[col].astype(str)
        continue
        
    # --- RÈGLES B : Variables Calculées (Pourcentages) ---
    elif "(%)" in col or col.startswith("Part") or col.startswith("Taux"):
        df[col] = pd.to_numeric(df[col], errors='coerce').round(1)
        
    # --- RÈGLES C : Variables Calculées (Indices & Densités) ---
    elif col.startswith("Densité") or col.startswith("Indice") or col.startswith("Taille") or col.startswith("Superficie"):
        df[col] = pd.to_numeric(df[col], errors='coerce').round(2)
        
    # --- CATÉGORIES 2 & 3 : Taux et Valeurs financières brutes (INSEE) ---
    elif col.startswith('TX') or col.endswith('LOY'):
        df[col] = pd.to_numeric(df[col], errors='coerce').round(2)
        
    # --- CATÉGORIE 1 & RÈGLE A : Tout le reste (Quantités physiques et Volumes) ---
    else:
        # Conversion en numérique, arrondi à l'entier, et cast en Int64 (qui supporte les NaN)
        df[col] = pd.to_numeric(df[col], errors='coerce').round(0).astype("Int64")
```