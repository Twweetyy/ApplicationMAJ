"""Extrait les lignes de Roubaix du fichier détail national FD_INDCVI (plusieurs Go).

    python scripts/extraire_indcvi_roubaix.py "chemin\\vers\\FD_INDCVI_2024.csv"

Le fichier national peut être en CSV ou en Parquet. La sortie garde le même nom et les
mêmes colonnes, en CSV : data/indcvi_roubaix/FD_INDCVI_AAAA.csv (quelques Mo), prête à
déposer dans le portail.
"""
import os
import sys

import pandas as pd

DOSSIER_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORTIE_DIR = os.path.join(DOSSIER_RACINE, "data", "indcvi_roubaix")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    source = sys.argv[1]
    if not os.path.isfile(source):
        print(f"Fichier introuvable : {source}")
        sys.exit(1)
    os.makedirs(SORTIE_DIR, exist_ok=True)
    sortie = os.path.join(SORTIE_DIR, os.path.splitext(os.path.basename(source))[0] + ".csv")

    if source.casefold().endswith(".parquet"):
        import duckdb

        chemin = source.replace("'", "''")
        bloc = duckdb.sql(
            f"SELECT COLUMNS(*)::VARCHAR FROM read_parquet('{chemin}') WHERE CAST(IRIS AS VARCHAR) LIKE '59512%'"
        ).df()
        bloc.to_csv(sortie, sep=";", index=False)
    else:
        premier = True
        for bloc in pd.read_csv(source, sep=";", dtype=str, chunksize=500_000):
            bloc = bloc[bloc["IRIS"].str.startswith("59512", na=False)]
            bloc.to_csv(sortie, sep=";", index=False, mode="w" if premier else "a", header=premier)
            premier = False
    print("OK :", sortie)


if __name__ == "__main__":
    main()
