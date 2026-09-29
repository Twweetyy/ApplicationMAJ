"""Persistance optionnelle des tables BDDMAS dans une base SQLAlchemy."""

import os
import re
import unicodedata


def _nom_table(nom_theme: str) -> str:
    nom_ascii = unicodedata.normalize("NFKD", nom_theme).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "_", nom_ascii).strip("_").lower()


def persister_dans_bddmas(dico_fichiers: dict) -> list[str]:
    """Écrit les tables si BDDMAS_DATABASE_URL est configurée dans l'environnement."""
    url = os.environ.get("BDDMAS_DATABASE_URL")
    if not url:
        print("Persistance SQL ignorée : variable BDDMAS_DATABASE_URL non définie")
        return []

    mode = os.environ.get("BDDMAS_IF_EXISTS", "fail").lower()
    if mode not in {"fail", "append", "replace"}:
        raise ValueError("BDDMAS_IF_EXISTS doit valoir fail, append ou replace.")

    try:
        from sqlalchemy import create_engine
    except ImportError as erreur:
        raise RuntimeError("SQLAlchemy est requis pour la persistance BDDMAS.") from erreur

    engine = create_engine(url)
    tables_ecrites = []
    try:
        with engine.begin() as connexion:
            for nom_theme, dataframe in dico_fichiers.items():
                if dataframe.empty:
                    continue
                nom_table = _nom_table(nom_theme)
                dataframe.to_sql(
                    nom_table,
                    connexion,
                    if_exists=mode,
                    index=False,
                )
                tables_ecrites.append(nom_table)
    finally:
        engine.dispose()

    print(f"Tables écrites dans la base BDDMAS : {', '.join(tables_ecrites)}")
    return tables_ecrites