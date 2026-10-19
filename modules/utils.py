"""Utility functions for the MAS ApplicationMAJ project.

This module currently provides a unified file reader `lire_fichier` that can read
both CSV files (using pandas) and Parquet files (using DuckDB).  The function
mirrors the signature of `pandas.read_csv` for CSV paths while delegating Parquet
reads to DuckDB's `parquet_scan`.

The implementation is deliberately lightweight – it only imports DuckDB when a
Parquet file is detected, avoiding an unnecessary heavy import for pure‑CSV
workflows.
"""

import os
from typing import Any

import pandas as pd


def _duckdb_read_parquet(chemin: str, **kwargs: Any) -> pd.DataFrame:
    """Read a Parquet file via DuckDB.

    Parameters
    ----------
    chemin: str
        Path to the Parquet file.
    **kwargs: Any
        Additional keyword arguments are accepted for API compatibility but are
        currently ignored because DuckDB's `parquet_scan` does not support the
        same options as `pd.read_csv`.

    Returns
    -------
    pd.DataFrame
        DataFrame containing the Parquet data.
    """
    import duckdb  # Imported lazily to avoid dependency overhead when not needed.

    # DuckDB can read Parquet directly via SQL. ``parquet_scan`` returns a table.
    # We construct a simple SELECT * query.
    query = f"SELECT * FROM parquet_scan('{chemin.replace('"', "''")}')"
    return duckdb.query(query).to_df()


def lire_fichier(chemin: str, nrows: int | None = None, sep: str = ",", encoding: str = "utf-8", **kwargs: Any) -> pd.DataFrame:
    """Unified reader for CSV and Parquet files.

    The function automatically detects the file extension and dispatches to the
    appropriate backend:

    * ``.csv`` – delegated to ``pandas.read_csv``.
    * ``.parquet`` – read with DuckDB via ``_duckdb_read_parquet``.

    Parameters are compatible with ``pandas.read_csv`` for CSV usage.  Extra
    ``kwargs`` are passed through to the underlying reader (ignored for Parquet).
    """
    _, ext = os.path.splitext(chemin.lower())
    if ext == ".parquet":
        # DuckDB handles row limiting via ``LIMIT``; we apply it manually if
        # ``nrows`` is provided.
        df = _duckdb_read_parquet(chemin, **kwargs)
        if nrows is not None:
            return df.head(nrows)
        return df
    else:
        # Assume CSV – defer to pandas. ``nrows`` maps to pandas' ``nrows``.
        return pd.read_csv(chemin, sep=sep, encoding=encoding, nrows=nrows, **kwargs)
