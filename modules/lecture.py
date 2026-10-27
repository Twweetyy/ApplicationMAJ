"""Lecture des fichiers de données d'un lot, au format CSV ou Parquet.

Les CSV sont lus par pandas, comme avant. Les Parquet sont lus par DuckDB, importé
seulement si un Parquet est présent : un lot 100 % CSV ne dépend pas de DuckDB.
Les métadonnées (meta_*.csv, varmod_*.csv) restent en CSV et ne passent pas par ici.
"""
import os
from collections.abc import Iterator

import pandas as pd

EXTENSIONS_DONNEES = (".csv", ".parquet")

# Types pandas demandés par l'appelant -> types DuckDB équivalents
_TYPES_DUCKDB = {str: "VARCHAR", "str": "VARCHAR", "float64": "DOUBLE", float: "DOUBLE"}


def est_fichier_donnees(nom: str) -> bool:
    """Vrai pour un fichier de données accepté (.csv ou .parquet), hors métadonnées."""
    nom = nom.casefold()
    return nom.endswith(EXTENSIONS_DONNEES) and not nom.startswith(("meta_", "varmod_"))


def est_parquet(chemin: str) -> bool:
    return chemin.casefold().endswith(".parquet")


def _requete_parquet(chemin: str, colonnes: list | None, types: dict | None) -> str:
    """SELECT sur le Parquet : colonnes demandées seulement, conversions de type faites par DuckDB.
    types ne doit citer que des colonnes du fichier (voir _types_existants)."""
    types = types or {}
    if colonnes is None:
        # Colonnes à convertir remplacées, les autres gardées telles quelles
        conversions = [
            f'CAST("{nom}" AS {_TYPES_DUCKDB[type_]}) AS "{nom}"'
            for nom, type_ in types.items()
            if type_ in _TYPES_DUCKDB
        ]
        selection = f"* REPLACE ({', '.join(conversions)})" if conversions else "*"
    else:
        selection = ", ".join(
            f'CAST("{nom}" AS {_TYPES_DUCKDB[types[nom]]}) AS "{nom}"'
            if types.get(nom) in _TYPES_DUCKDB
            else f'"{nom}"'
            for nom in colonnes
        )
    source = chemin.replace("'", "''")
    return f"SELECT {selection} FROM read_parquet('{source}')"


def _executer_parquet(chemin: str, requete: str):
    import duckdb

    connexion = duckdb.connect()
    try:
        return connexion, connexion.execute(requete)
    except duckdb.Error as erreur:
        connexion.close()
        raise ValueError(f"Parquet illisible ({os.path.basename(chemin)}) : {erreur}") from erreur


def lire_entetes(chemin: str, sep: str = ";") -> list[str]:
    """Noms des colonnes, sans lire les lignes."""
    if not est_parquet(chemin):
        return list(pd.read_csv(chemin, sep=sep, nrows=0, encoding="utf-8-sig").columns)
    connexion, resultat = _executer_parquet(chemin, _requete_parquet(chemin, None, None) + " LIMIT 0")
    with connexion:
        return [colonne[0] for colonne in resultat.description]


def compter_lignes(chemin: str) -> int | None:
    """Nombre exact de lignes d'un Parquet (lu dans ses métadonnées) ; None pour un CSV."""
    if not est_parquet(chemin):
        return None
    source = chemin.replace("'", "''")
    connexion, resultat = _executer_parquet(chemin, f"SELECT COUNT(*) FROM read_parquet('{source}')")
    with connexion:
        return resultat.fetchone()[0]


def _types_existants(chemin: str, types: dict | None) -> dict:
    """Garde seulement les types des colonnes présentes (comme pandas, qui ignore les absentes)."""
    if not types:
        return {}
    entetes = set(lire_entetes(chemin))
    return {nom: type_ for nom, type_ in types.items() if nom in entetes}


def lire_table(
    chemin: str,
    sep: str = ";",
    usecols: list | None = None,
    dtype: dict | None = None,
    **options_csv,
) -> pd.DataFrame:
    """Lit tout le fichier. options_csv (encoding, low_memory…) ne servent qu'aux CSV."""
    if not est_parquet(chemin):
        return pd.read_csv(chemin, sep=sep, usecols=usecols, dtype=dtype, **options_csv)
    requete = _requete_parquet(chemin, usecols, _types_existants(chemin, dtype))
    connexion, resultat = _executer_parquet(chemin, requete)
    with connexion:
        return resultat.df()


def lire_par_blocs(
    chemin: str,
    taille_bloc: int,
    sep: str = ";",
    usecols: list | None = None,
    dtype: dict | None = None,
    **options_csv,
) -> Iterator[pd.DataFrame]:
    """Lit le fichier par blocs d'environ taille_bloc lignes, sans tout charger en mémoire."""
    if not est_parquet(chemin):
        yield from pd.read_csv(chemin, sep=sep, usecols=usecols, dtype=dtype, chunksize=taille_bloc, **options_csv)
        return
    requete = _requete_parquet(chemin, usecols, _types_existants(chemin, dtype))
    connexion, resultat = _executer_parquet(chemin, requete)
    # DuckDB rend des vecteurs de 2 048 lignes
    vecteurs_par_bloc = max(1, taille_bloc // 2048)
    with connexion:
        while True:
            bloc = resultat.fetch_df_chunk(vecteurs_par_bloc)
            if bloc.empty:
                break
            yield bloc
