#!/usr/bin/env python3
"""adapt_2023.py

Script d’assistance locale pour adapter le pipeline BDDMAS aux jeux de données 2023.

Fonctionnalités principales :
1️⃣ Parcourt le répertoire ``data`` à la recherche de fichiers CSV (ou Parquet) contenant l’année 2023 dans leur nom.
2️⃣ Lit les en‑têtes de chaque fichier et compare avec les métadonnées existantes (``meta_*.csv``) et les dictionnaires de variables (``dictionnaire_variables*.yml``).
3️⃣ Génère automatiquement des entrées méta pour les nouvelles colonnes : code de colonne → libellé auto‑généré.
4️⃣ Met à jour les dictionnaires YAML avec les nouveaux mappings éventuels.
5️⃣ Signale les colonnes obligatoires manquantes (``IRIS``, ``CODGEO``, ``COM`` pour les fichiers thématiques ; ``IRIS``, ``AGEREV``, ``AGED``, ``IPONDI`` pour les micro‑données enfants).
6️⃣ Re‑génère le modèle Excel final en copiant le modèle existant et en ajoutant les nouvelles colonnes tout en conservant le style.

Le script ne modifie aucun fichier existant sans confirmation : il crée d’abord des copies temporaires et affiche un résumé des modifications proposées.

Utilisation :
    cd "\\srvsig03p\Partage_SIG\Opendata\Alternants\Bilal 2026-2027\MAS\ApplicationMAJ"
    python adapt_2023.py

Après vérification du résumé, confirmez en tapant ``y`` pour appliquer les changements.
"""

import os
import sys
import csv
import yaml
import pandas as pd
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
DICTIONARIES_DIR = PROJECT_ROOT / "dictionnaires"
META_DIR = DICTIONARIES_DIR / "meta"
MODEL_XLSX = PROJECT_ROOT / "TAB_BDDMAS_INSEE2022_MODELE.xlsx"
OUTPUT_XLSX = PROJECT_ROOT / "TAB_BDDMAS_INSEE2022_Tout_perimetre_2023.xlsx"

# Colonnes obligatoires par type de fichier
MANDATORY_GEOG = {"IRIS", "CODGEO", "COM"}
MANDATORY_CHILD = {"IRIS", "AGEREV", "AGED", "IPONDI"}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def save_yaml(data: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

def normaliser(col: str) -> str:
    """Normalise un nom de colonne comme le fait le pipeline (strip + casefold)."""
    return col.strip().casefold()

def find_meta_file(data_file: Path) -> Path | None:
    """Cherche le méta correspondant.
    Exemple : data ``base-ic-activite-residents-2023.CSV`` →
    méta ``meta_activite_residents.csv`` (présent dans ``dictionnaires/meta``).
    """
    base = data_file.stem  # sans extension
    # Retire l’année éventuelle
    parts = base.split("-")
    if parts[-1].isdigit() and len(parts[-1]) == 4:
        parts = parts[:-1]
    candidate = "_".join(parts[2:])  # on enlève les préfixes "base" "ic"
    if not candidate:
        return None
    for meta in META_DIR.glob("meta_*.csv"):
        if candidate in meta.stem:
            return meta
    return None

def read_meta(path: Path) -> dict:
    if not path.is_file():
        return {}
    df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8-sig")
    # on attend les colonnes COD_VAR / LIB_VAR
    if {"COD_VAR", "LIB_VAR"}.issubset(df.columns):
        return dict(zip(df["COD_VAR"].astype(str), df["LIB_VAR"].astype(str)))
    return {}

try:
    from modules.llm_wrapper import appeler_llm
except ImportError:
    appeler_llm = None

def generer_libelle_ia(colonne: str, theme: str = "") -> str:
    """Génère un libellé clair et concis en français via le LLM pour une colonne Insee."""
    if not appeler_llm:
        return f"Variable {colonne}"
    prompt = (
        f"Tu es un expert SIG et démographie Insee pour la Ville de Roubaix. "
        f"Donne une description brève et professionnelle en français (1 phrase, max 20 mots) "
        f"pour la variable Insee nommée '{colonne}' (Thème : {theme}). "
        f"Réponds UNIQUEMENT avec la description, sans guillemets ni préambule."
    )
    try:
        desc = appeler_llm(prompt, max_tokens=100)
        return desc.strip().strip('"').strip("'")
    except Exception as e:
        print(f"  [IA fallback] Impossible de contacter le LLM : {e}")
        return f"Variable {colonne} (mésestimation LLM)"

def append_meta(path: Path, new_cols: list[str], theme: str = "") -> None:
    """Ajoute des lignes au méta avec une description générée par l'IA."""
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        for col in new_cols:
            print(f"  🤖 Demande de description à l'IA pour '{col}'...")
            desc = generer_libelle_ia(col, theme=theme)
            print(f"     -> {desc}")
            writer.writerow([col, desc])

def load_dictionary_yaml() -> dict:
    path = DICTIONARIES_DIR / "dictionnaire_variables.yml"
    return load_yaml(path)

def save_dictionary_yaml(data: dict) -> None:
    path = DICTIONARIES_DIR / "dictionnaire_variables.yml"
    save_yaml(data, path)

def update_dictionary(new_cols: list[str]) -> None:
    """Ajoute des mappings ``col: col`` pour les nouvelles colonnes si elles n’existent pas déjà."""
    dico = load_dictionary_yaml()
    changed = False
    for col in new_cols:
        if col not in dico:
            dico[col] = col
            changed = True
    if changed:
        save_dictionary_yaml(dico)

def copy_model_and_extend(new_columns: dict) -> None:
    """Copie le modèle Excel et insère les nouvelles colonnes dans la première feuille.
    Les nouvelles colonnes sont ajoutées à droite des colonnes existantes.
    Le style du tableau est conservé grâce à ``openpyxl``.
    """
    try:
        from openpyxl import load_workbook
    except ImportError:
        print("openpyxl n'est pas installé – le modèle Excel ne sera pas mis à jour.")
        return

    wb = load_workbook(MODEL_XLSX)
    ws = wb.active
    # Trouve la dernière colonne remplie dans la première ligne
    max_col = ws.max_column
    for theme, cols in new_columns.items():
        for col in cols:
            max_col += 1
            cell = ws.cell(row=1, column=max_col, value=col)
            # Copie le style de la première cellule (A1) pour garder la mise en forme
            cell._style = ws.cell(row=1, column=1)._style
    wb.save(OUTPUT_XLSX)
    print(f"Modèle Excel mis à jour → {OUTPUT_XLSX}")

# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def main():
    if not DATA_DIR.is_dir():
        print(f"Répertoire data introuvable : {DATA_DIR}")
        sys.exit(1)

    files_2023 = [p for p in DATA_DIR.iterdir() if p.is_file() and "2023" in p.stem and p.suffix.lower() in {".csv", ".parquet"}]
    if not files_2023:
        print("Aucun fichier 2023 trouvé dans le répertoire data.")
        sys.exit(0)

    summary = {}
    for file_path in files_2023:
        print(f"\n--- Analyse de {file_path.name} ---")
        # Lecture de l’entête uniquement (performance)
        try:
            if file_path.suffix.lower() == ".parquet":
                df_header = pd.read_parquet(file_path, engine="pyarrow", columns=None).head(0)
            else:
                df_header = pd.read_csv(file_path, nrows=0, sep=";", encoding="utf-8-sig")
        except Exception as e:
            print(f"Erreur de lecture du fichier : {e}")
            continue
        cols = [c for c in df_header.columns]
        norm_cols = {normaliser(c) for c in cols}
        print(f"Colonnes détectées ({len(cols)}) : {cols}")

        # Détermination du type (perimetre, enfants, theme)
        if "perimetresmas" in normaliser(file_path.stem):
            role = "perimetre"
        elif "fdindcvi" in normaliser(file_path.stem):
            role = "microdonnees_enfants"
        else:
            role = "theme"
        print(f"Rôle détecté : {role}")

        # Vérifications obligatoires
        missing = []
        if role == "perimetre" or role == "theme":
            missing = [c for c in MANDATORY_GEOG if normaliser(c) not in norm_cols]
        elif role == "microdonnees_enfants":
            missing = [c for c in MANDATORY_CHILD if normaliser(c) not in norm_cols]
        if missing:
            print(f"⚠️ Colonnes obligatoires manquantes : {missing}")
        else:
            print("✅ Toutes les colonnes obligatoires sont présentes.")

        # Méta association
        meta_path = find_meta_file(file_path)
        if meta_path:
            meta_dict = read_meta(meta_path)
            existing = set(meta_dict.keys())
            new_cols = [c for c in cols if c not in existing]
            if new_cols:
                print(f"🔧 Colonnes nouvelles non présentes dans le méta {meta_path.name} : {new_cols}")
                append_meta(meta_path, new_cols, theme=file_path.stem)
                print(f"   → méta mis à jour.")
            else:
                print("✅ Méta déjà à jour.")
        else:
            print("⚠️ Aucun fichier méta correspondant trouvé – aucune mise à jour méta.")
            new_cols = []

        # Dictionnaire variables
        if new_cols:
            update_dictionary(new_cols)
            print("✅ Dictionnaire variables.yml mis à jour avec les nouvelles colonnes.")

        # Accumuler les nouvelles colonnes par thème pour le modèle Excel
        theme_key = file_path.stem.split("-")[0] if role == "theme" else role
        summary.setdefault(theme_key, []).extend(new_cols)

    # Mise à jour du modèle Excel (optionnelle)
    if summary:
        print("\n--- Mise à jour du modèle Excel ---")
        copy_model_and_extend(summary)
    else:
        print("Aucune nouvelle colonne à intégrer dans le modèle Excel.")

    print("\n=== Résumé des modifications ===")
    for k, v in summary.items():
        if v:
            print(f"{k}: {len(v)} nouvelle(s) colonne(s) – {v}")
    print("\nFin du script.")

if __name__ == "__main__":
    main()
