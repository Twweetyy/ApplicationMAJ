"""Export des tables attributaires BDDMAS pour les croisements SIG par IRIS."""

import re
import unicodedata
from pathlib import Path

import pandas as pd


def _nom_fichier(nom_theme: str) -> str:
    nom_ascii = unicodedata.normalize("NFKD", nom_theme).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "_", nom_ascii).strip("_").lower()


def exporter_tables_sig(dico_fichiers: dict, dossier_sortie: str) -> list[Path]:
    """Écrit un CSV UTF-8 par thème, avec IRIS comme première colonne de jointure."""
    destination = Path(dossier_sortie)
    destination.mkdir(parents=True, exist_ok=True)
    fichiers_crees = []

    for nom_theme, dataframe in dico_fichiers.items():
        if "IRIS" not in dataframe.columns:
            print(f"Export SIG ignoré pour {nom_theme} : colonne IRIS absente")
            continue

        table = dataframe.copy()
        table["IRIS"] = table["IRIS"].astype(str).str.zfill(9)
        colonnes = ["IRIS", *[col for col in table.columns if col != "IRIS"]]
        chemin = destination / f"{_nom_fichier(nom_theme)}.csv"
        table[colonnes].to_csv(chemin, sep=";", index=False, encoding="utf-8-sig")
        fichiers_crees.append(chemin)

    return fichiers_crees