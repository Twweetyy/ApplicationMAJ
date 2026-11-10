"""Extrait les lignes de Roubaix (ou de la MEL) du fichier détail national FD_INDCVI (plusieurs Go).

    python scripts/extraire_indcvi_roubaix.py "chemin\\vers\\FD_INDCVI_2024.csv"
    python scripts/extraire_indcvi_roubaix.py "chemin\\vers\\FD_INDCVI_2024.csv" --perimetre mel

Le fichier national peut être en CSV ou en Parquet. La sortie garde le même nom et les
mêmes colonnes, en CSV, prête à déposer dans le portail :
- Roubaix : data/indcvi_roubaix/FD_INDCVI_AAAA.csv (quelques Mo) ;
- MEL : data/indcvi_mel/FD_INDCVI_AAAA.csv (lignes dont l'IRIS est dans une commune de
  dictionnaires/communes_mel.yml).

Le FD_INDCVI ne renseigne l'IRIS que pour les communes découpées en IRIS : les petites
communes de la MEL (IRIS « ZZZZZZZZZ ») n'y figurent donc pas.
"""
import argparse
import os

import pandas as pd
import yaml

DOSSIER_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FICHIER_COMMUNES_MEL = os.path.join(DOSSIER_RACINE, "dictionnaires", "communes_mel.yml")
DOSSIERS_SORTIE = {
    "roubaix": os.path.join(DOSSIER_RACINE, "data", "indcvi_roubaix"),
    "mel": os.path.join(DOSSIER_RACINE, "data", "indcvi_mel"),
}


def codes_communes(perimetre: str) -> list[str]:
    """Codes commune retenus (5 premiers caractères du code IRIS)."""
    if perimetre == "roubaix":
        return ["59512"]
    with open(FICHIER_COMMUNES_MEL, "r", encoding="utf-8") as fichier:
        return sorted(str(code).strip() for code in (yaml.safe_load(fichier) or {}))


def main():
    parser = argparse.ArgumentParser(description="Extrait Roubaix ou la MEL du FD_INDCVI national.")
    parser.add_argument("source", help="Fichier FD_INDCVI national (CSV ou Parquet)")
    parser.add_argument("--perimetre", choices=sorted(DOSSIERS_SORTIE), default="roubaix")
    arguments = parser.parse_args()

    source = arguments.source
    if not os.path.isfile(source):
        parser.exit(1, f"Fichier introuvable : {source}\n")
    codes = codes_communes(arguments.perimetre)
    sortie_dir = DOSSIERS_SORTIE[arguments.perimetre]
    os.makedirs(sortie_dir, exist_ok=True)
    sortie = os.path.join(sortie_dir, os.path.splitext(os.path.basename(source))[0] + ".csv")

    if source.casefold().endswith(".parquet"):
        import duckdb

        chemin = source.replace("'", "''")
        bloc = duckdb.execute(
            f"SELECT COLUMNS(*)::VARCHAR FROM read_parquet('{chemin}') "
            "WHERE substr(CAST(IRIS AS VARCHAR), 1, 5) IN (SELECT unnest(?))",
            [codes],
        ).df()
        bloc.to_csv(sortie, sep=";", index=False)
        nombre_lignes = len(bloc)
    else:
        premier = True
        nombre_lignes = 0
        for bloc in pd.read_csv(source, sep=";", dtype=str, chunksize=500_000):
            bloc = bloc[bloc["IRIS"].str[:5].isin(codes)]
            bloc.to_csv(sortie, sep=";", index=False, mode="w" if premier else "a", header=premier)
            premier = False
            nombre_lignes += len(bloc)
    print(f"OK : {sortie} ({nombre_lignes} lignes)")


if __name__ == "__main__":
    main()
