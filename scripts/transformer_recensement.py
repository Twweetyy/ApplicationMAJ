#!/usr/bin/env python3
"""
transformer_recensement.py
==========================
Convertit les cubes multidimensionnels Insee du recensement (format long / SDMX,
publié depuis le RP 2023) en tables plates infracommunales (format large) pour la
Ville de Roubaix (38 IRIS).

Le millésime n'est pas fixé : chaque dossier data/dataAAAA/sources_brutes_insee/
contenant des cubes base-ic-{pop,log,emp,men,dip}-AAAA est traité. Les codes de
variables prennent le préfixe de l'année (P23_, P24_…).

Chaque cube brut peut être fourni en CSV ou en Parquet (base-ic-pop-AAAA.csv ou
base-ic-pop-AAAA.parquet) ; le Parquet est préféré s'il est présent (lecture DuckDB).

Produit, dans data/dataAAAA/, les 5 fichiers de données requis par le portail BDDMAS :
  - base-ic-evol-struct-pop-AAAA.CSV
  - base-ic-activite-residents-AAAA.CSV
  - base-ic-logement-AAAA.CSV
  - base-ic-couples-familles-menages-AAAA.CSV
  - base-ic-diplomes-formation-AAAA.CSV
et leurs 5 métadonnées dans dictionnaires/meta/metaAAAA/.

Les fichiers complémentaires Insee (DS_RP_POPULATION_COMP, DS_RP_EMPLOI_LR_COMP,
DS_RP_ACTIVITE_PRINC, DS_RP_NAVETTES_PRINC, DS_RP_MENAGES_COMP, DS_RP_FAMILLE_COMP,
DS_RP_EDUCATION_PRINC, DS_RP_LOGEMENT_COMP, suffixés _IRIS_AAAA), déposés sous leur
nom Insee dans data/dataAAAA/complementaires/, ajoutent les colonnes du modèle 2022
absentes des cubes principaux (CSP, familles, salariés, lieu de travail, transport,
scolarisation, occupation des logements). Chacun est facultatif.

    python scripts/transformer_recensement.py              # tous les millésimes présents
    python scripts/transformer_recensement.py --annee 2024 # un seul millésime
    python scripts/transformer_recensement.py --force      # recalcule même si à jour
"""

import argparse
import os
import re
import pandas as pd
import numpy as np
import yaml
import sys

# ---------------------------------------------------------------------------
# Dossiers
# ---------------------------------------------------------------------------
DOSSIER_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_DATA = os.path.join(DOSSIER_RACINE, "data")

NB_IRIS_ROUBAIX = 38
THEMES_SOURCES = ["pop", "log", "emp", "men", "dip"]
# Noms des fichiers produits, sans l'année (ordre : POP, LOG, ACT RES, COU FAM, DIP)
BASES_SORTIES = [
    "base-ic-evol-struct-pop",
    "base-ic-logement",
    "base-ic-activite-residents",
    "base-ic-couples-familles-menages",
    "base-ic-diplomes-formation",
]


def dossier_sources(annee):
    return os.path.join(DOSSIER_DATA, f"data{annee}", "sources_brutes_insee")


def dossier_sortie_data(annee):
    return os.path.join(DOSSIER_DATA, f"data{annee}")


def dossier_sortie_meta(annee):
    return os.path.join(DOSSIER_RACINE, "dictionnaires", "meta", f"meta{annee}")


def noms_sorties(annee):
    """(fichier de données, fichier méta) produits pour un millésime."""
    return [(f"{base}-{annee}.CSV", f"meta_{base}-{annee}.csv") for base in BASES_SORTIES]


def millesimes_disponibles():
    """Années ayant au moins un cube brut dans data/dataAAAA/sources_brutes_insee/."""
    annees = set()
    if not os.path.isdir(DOSSIER_DATA):
        return []
    for nom_dossier in os.listdir(DOSSIER_DATA):
        trouve = re.fullmatch(r"data(\d{4})", nom_dossier)
        if not trouve or not os.path.isdir(dossier_sources(trouve.group(1))):
            continue
        annee = trouve.group(1)
        motif = re.compile(rf"base-ic-({'|'.join(THEMES_SOURCES)})-{annee}\.(csv|parquet)", re.IGNORECASE)
        if any(motif.fullmatch(nom) for nom in os.listdir(dossier_sources(annee))):
            annees.add(annee)
    return sorted(annees)


def avec_millesime(code, annee):
    """P23_POP -> P24_POP pour le millésime 2024 : les codes sont écrits pour 2023 dans ce script."""
    return re.sub(r"^([PC])23_", lambda m: f"{m.group(1)}{int(annee) % 100:02d}_", str(code))


def sorties_a_jour(annee):
    """Vrai si les 10 fichiers produits existent, comptent 38 IRIS et sont plus
    récents que les sources Insee et que ce script."""
    sorties = []
    for nom_data, nom_meta in noms_sorties(annee):
        sorties.append(os.path.join(dossier_sortie_data(annee), nom_data))
        sorties.append(os.path.join(dossier_sortie_meta(annee), nom_meta))
    if not all(os.path.exists(chemin) for chemin in sorties):
        return False
    entrees = [
        os.path.join(dossier_sources(annee), f"base-ic-{theme}-{annee}{extension}")
        for theme in THEMES_SOURCES
        for extension in (".csv", ".parquet")
    ]
    entrees += [
        chemin_complementaire(nom, annee) for fichiers in COMPLEMENTAIRES.values() for nom, _ in fichiers
    ]
    entrees = [c for c in entrees if c and os.path.exists(c)] + [os.path.abspath(__file__)]
    if min(map(os.path.getmtime, sorties)) < max(map(os.path.getmtime, entrees)):
        return False
    for nom_data, _ in noms_sorties(annee):
        df = pd.read_csv(os.path.join(dossier_sortie_data(annee), nom_data), sep=";", dtype=str, encoding="utf-8-sig")
        if len(df) != NB_IRIS_ROUBAIX:
            return False
    return True


# Load allowed GEO codes from grand_quartier.yml (full IRIS codes for Roubaix)
GRAND_QUARTIER_PATH = os.path.join(DOSSIER_RACINE, "dictionnaires", "grand_quartier.yml")
with open(GRAND_QUARTIER_PATH, "r", encoding="utf-8") as f:
    ALLOWED_GEO = {str(k) for k in yaml.safe_load(f).keys()}

# Colonnes qui ne sont pas des dimensions du cube (identifiants, libellés, mesure, statut)
COLONNES_NON_DIMENSION = {
    "GEO", "GEO_OBJECT", "OBS_VALUE", "OBS_STATUS", "TIME_PERIOD", "FREQ",
    "TRIRIS", "LARGE_DISTRICT", "RP_MEASURE", "TYP_IRIS", "LAB_IRIS",
    "Type d'IRIS", "Label de l'IRIS",
}

def valeur_cube(iris_df, res, filtre):
    """Somme OBS_VALUE par IRIS pour un filtre donné.

    Les cubes Insee 2023 croisent plusieurs dimensions : toute dimension non citée
    dans le filtre est ramenée à son total "_T" (quand il existe) pour ne pas
    additionner plusieurs fois les mêmes personnes ou logements.
    """
    sub = iris_df
    for k, v in filtre.items():
        if isinstance(v, list):
            sub = sub[sub[k].isin(v)]
        else:
            sub = sub[sub[k] == v]
    for col in sub.columns:
        if col in COLONNES_NON_DIMENSION or col in filtre:
            continue
        if (sub[col].astype(str) == "_T").any():
            sub = sub[sub[col].astype(str) == "_T"]
    s = sub.groupby("GEO")["OBS_VALUE"].sum()
    return res["IRIS"].map(s).fillna(0.0)

def chemin_source(theme, annee):
    """Cube brut du thème : le Parquet s'il existe (plus léger et plus rapide), sinon le CSV."""
    base = os.path.join(dossier_sources(annee), f"base-ic-{theme}-{annee}")
    return base + ".parquet" if os.path.exists(base + ".parquet") else base + ".csv"


def _lire_roubaix_parquet(chemin_parquet):
    """Lignes de Roubaix d'un cube Parquet, filtrées par DuckDB, toutes les colonnes en texte (comme le CSV)."""
    import duckdb

    codes = ", ".join("'" + code.replace("'", "''") + "'" for code in sorted(ALLOWED_GEO))
    source = chemin_parquet.replace("'", "''")
    return duckdb.sql(
        f"SELECT COLUMNS(*)::VARCHAR FROM read_parquet('{source}') WHERE CAST(GEO AS VARCHAR) IN ({codes})"
    ).df()


def charger_roubaix(chemin_source):
    """Charge et filtre uniquement les lignes de Roubaix (GEO dans ALLOWED_GEO), depuis un CSV ou un Parquet."""
    print(f"  -> Lecture et filtrage de {os.path.basename(chemin_source)}...")
    if chemin_source.casefold().endswith(".parquet"):
        chunks = [_lire_roubaix_parquet(chemin_source)]
        chunks = [m for m in chunks if not m.empty]
    else:
        chunks = []
        for chunk in pd.read_csv(chemin_source, sep=";", chunksize=100000, dtype=str):
            m = chunk[chunk["GEO"].astype(str).isin(ALLOWED_GEO)]
            if not m.empty:
                chunks.append(m)
    if not chunks:
        raise ValueError(f"Aucune ligne pour Roubaix dans {chemin_source}")
    df = pd.concat(chunks, ignore_index=True)
    df["GEO"] = df["GEO"].astype(str)
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce").fillna(0.0)
    return df

def extraire_socle_geo(df_source):
    """Extrait le socle géographique des IRIS de Roubaix (IRIS, COM, TYP_IRIS, LAB_IRIS)."""
    iris_rows = df_source[df_source["GEO_OBJECT"] == "IRIS"] if "GEO_OBJECT" in df_source.columns else df_source
    iris_rows = iris_rows[iris_rows["GEO"].astype(str).str.len() == 9]
    socle = iris_rows.groupby("GEO").first().reset_index()
    socle["IRIS"] = socle["GEO"].astype(str)
    socle["COM"] = "59512"
    socle["TYP_IRIS"] = socle.get("TYP_IRIS", "H")
    socle["LAB_IRIS"] = socle.get("LAB_IRIS", "2")
    return socle[["IRIS", "COM", "TYP_IRIS", "LAB_IRIS"]].drop_duplicates("IRIS").sort_values("IRIS").reset_index(drop=True)

# ==============================================================================
# 1. POPULATION (POP)
# ==============================================================================
def transformer_population(df_raw, socle):
    print("Traitement du thème POPULATION (POP)...")
    res = socle.copy()
    iris_df = df_raw[df_raw["GEO"].astype(str).isin(res["IRIS"])]
    
    def get_val(filtre):
        return valeur_cube(iris_df, res, {"RP_MEASURE": "POP", **filtre})

    # Indicateurs Population
    colonnes_pop = {
        "P23_POP": {"SEX": "_T", "AGE": "_T", "IMMI": "_T", "NATIONALITY_TYPE": "_T", "HAR": "_T"},
        "P23_POP0002": {"AGE": "Y_LT2"},
        "P23_POP0305": {"AGE": "Y2T5"},
        "P23_POP0610": {"AGE": "Y6T10"},
        "P23_POP1117": {"AGE": ["Y11T14", "Y15T17"]},
        "P23_POP1824": {"AGE": "Y18T24"},
        "P23_POP2539": {"AGE": "Y25T39"},
        "P23_POP4054": {"AGE": "Y40T54"},
        "P23_POP5564": {"AGE": "Y55T64"},
        "P23_POP6579": {"AGE": "Y65T79"},
        "P23_POP80P": {"AGE": "Y_GE80"},
        "P23_POP0014": {"AGE": "Y_LT15"},
        "P23_POP1524": {"AGE": "Y15T24"},
        "P23_POP0019": {"AGE": "Y_LT20"},
        "P23_POP2064": {"AGE": "Y20T64"},
        "P23_POP65P": {"AGE": "Y_GE65"},
        "P23_POPH": {"SEX": "M", "AGE": "_T", "IMMI": "_T", "NATIONALITY_TYPE": "_T", "HAR": "_T"},
        "P23_H0014": {"SEX": "M", "AGE": "Y_LT15"},
        "P23_H1524": {"SEX": "M", "AGE": "Y15T24"},
        "P23_H0019": {"SEX": "M", "AGE": "Y_LT20"},
        "P23_H2064": {"SEX": "M", "AGE": "Y20T64"},
        "P23_H65P": {"SEX": "M", "AGE": "Y_GE65"},
        "P23_POPF": {"SEX": "F", "AGE": "_T", "IMMI": "_T", "NATIONALITY_TYPE": "_T", "HAR": "_T"},
        "P23_F0014": {"SEX": "F", "AGE": "Y_LT15"},
        "P23_F1524": {"SEX": "F", "AGE": "Y15T24"},
        "P23_F0019": {"SEX": "F", "AGE": "Y_LT20"},
        "P23_F2064": {"SEX": "F", "AGE": "Y20T64"},
        "P23_F65P": {"SEX": "F", "AGE": "Y_GE65"},
        "P23_POP_FR": {"NATIONALITY_TYPE": "250"},
        "P23_POP_ETR": {"NATIONALITY_TYPE": "100"},
        "P23_POP_IMM": {"IMMI": "1"},
        "P23_PMEN": {"HAR": "01"},
        "P23_PHORMEN": {"HAR": "11T23"},
    }

    meta_rows = [
        ("COM", "Commune ou ARM"),
        ("TYP_IRIS", "Type d'Iris"),
        ("LAB_IRIS", "Label de l'Iris"),
        ("P23_POP", "Population"),
        ("P23_POP0002", "Pop 0-2 ans"),
        ("P23_POP0305", "Pop 3-5 ans"),
        ("P23_POP0610", "Pop 6-10 ans"),
        ("P23_POP1117", "Pop 11-17 ans"),
        ("P23_POP1824", "Pop 18-24 ans"),
        ("P23_POP2539", "Pop 25-39 ans"),
        ("P23_POP4054", "Pop 40-54 ans"),
        ("P23_POP5564", "Pop 55-64 ans"),
        ("P23_POP6579", "Pop 65-79 ans"),
        ("P23_POP80P", "Pop 80 ans ou plus"),
        ("P23_POP0014", "Pop 0-14 ans"),
        ("P23_POP1524", "Pop 15-24 ans"),
        ("P23_POP0019", "Pop 0-19 ans"),
        ("P23_POP2064", "Pop 20-64 ans"),
        ("P23_POP65P", "Pop 65 ans ou plus"),
        ("P23_POPH", "Pop Hommes"),
        ("P23_H0014", "Pop Hommes 0-14 ans"),
        ("P23_H1524", "Pop Hommes 15-24 ans"),
        ("P23_H0019", "Pop Hommes 0-19 ans"),
        ("P23_H2064", "Pop Hommes 20-64 ans"),
        ("P23_H65P", "Pop Hommes 65 ans ou plus"),
        ("P23_POPF", "Pop Femmes"),
        ("P23_F0014", "Pop Femmes 0-14 ans"),
        ("P23_F1524", "Pop Femmes 15-24 ans"),
        ("P23_F0019", "Pop Femmes 0-19 ans"),
        ("P23_F2064", "Pop Femmes 20-64 ans"),
        ("P23_F65P", "Pop Femmes 65 ans ou plus"),
        ("P23_POP_FR", "Pop Français"),
        ("P23_POP_ETR", "Pop Etrangers"),
        ("P23_POP_IMM", "Pop Immigrés"),
        ("P23_PMEN", "Pop ménages"),
        ("P23_PHORMEN", "Pop hors ménages"),
    ]

    for col, filt in colonnes_pop.items():
        res[col] = get_val(filt)
    # Renommer les colonnes en enlevant le préfixe 'P23_'
    col_mapping = {col: col.replace('P23_', '') for col in colonnes_pop.keys()}
    res = res.rename(columns=col_mapping)
    # Mettre à jour les métadonnées en fonction du nouveau nom
    meta_rows = [(col_mapping.get(col, col), lib) for col, lib in meta_rows]
    return res, meta_rows

# ==============================================================================
# 2. LOGEMENT (LOG)
# ==============================================================================
def transformer_logement(df_raw, socle):
    print("Traitement du thème LOGEMENT (LOG)...")
    res = socle.copy()
    iris_df = df_raw[df_raw["GEO"].astype(str).isin(res["IRIS"])]

    def get_val(filtre):
        return valeur_cube(iris_df, res, {"RP_MEASURE": "DWELLINGS", **filtre})

    colonnes_log = {
        "P23_LOG": {"OCS": "_T"},
        "P23_RP": {"OCS": "DW_MAIN"},
        "P23_MEN": {"OCS": "DW_MAIN"},
        "P23_PMEN": {"OCS": "DW_MAIN", "RP_MEASURE": "DWELLINGS_POPSIZE"},
        "P23_RSECOCC": {"OCS": "DW_SEC_DW_OCC"},
        "P23_LOGVAC": {"OCS": "DW_VAC"},
        "P23_MAISON": {"TDW": "1"},
        "P23_APPART": {"TDW": "2"},
        "P23_RP_1P": {"NOR": "R1"},
        "P23_RP_2P": {"NOR": "R2"},
        "P23_RP_3P": {"NOR": "R3"},
        "P23_RP_4P": {"NOR": "R4"},
        "P23_RP_5PP": {"NOR": "R_GE5"},
        "P23_RP_M30M2": {"UFS": "LT30"},
        "P23_RP_3040M2": {"UFS": "30T39"},
        "P23_RP_4060M2": {"UFS": "40T59"},
        "P23_RP_6080M2": {"UFS": "60T79"},
        "P23_RP_80100M2": {"UFS": "80T99"},
        "P23_RP_100120M2": {"UFS": "100T119"},
        "P23_RP_120M2P": {"UFS": "GE120"},
        "P23_RP_ACH1919": {"BUILD_END": "Y_LT1919"},
        "P23_RP_ACH1945": {"BUILD_END": "Y1919T1945"},
        "P23_RP_ACH1970": {"BUILD_END": "Y1946T1970"},
        "P23_RP_ACH1990": {"BUILD_END": "Y1971T1990"},
        "P23_RP_ACH2005": {"BUILD_END": "Y1991T2005"},
        "P23_RP_ACH2019": {"BUILD_END": "Y2006TAAAA"},
        "P23_MEN_ANEM0002": {"L_STAY": "Y_LT2"},
        "P23_MEN_ANEM0204": {"L_STAY": "Y2T4"},
        "P23_MEN_ANEM0509": {"L_STAY": "Y5T9"},
        "P23_MEN_ANEM10P": {"L_STAY": "Y_GE10"},
        "P23_RP_PROP": {"TSH": "100"},
        "P23_RP_LOC": {"TSH": "200"},
        "P23_RP_LOCHLMV": {"TSH": "221"},
        "P23_RP_GRAT": {"TSH": "300"},
        "P23_RP_VOIT1": {"CARS": "C1"},
        "P23_RP_VOIT2P": {"CARS": "C_GE2"},
        "P23_RP_VOIT1P": {"CARS": "C_GE1"},
        "P23_RP_GARL": {"CARPARK": "1"},
        "P23_RP_CGAZV": {"NRG_SRC": "TOWN_GAS"},
        "P23_RP_CFIOUL": {"NRG_SRC": "OIL"},
        "P23_RP_CELEC": {"NRG_SRC": "ELC"},
        "P23_RP_CGAZB": {"NRG_SRC": "BOT_GAS"},
        "P23_RP_CAUT": {"NRG_SRC": "OTH"},
    }

    meta_rows = [
        ("COM", "Commune ou ARM"),
        ("TYP_IRIS", "Type d'Iris"),
        ("LAB_IRIS", "Label de l'Iris"),
        ("P23_LOG", "Logements"),
        ("P23_RP", "Résidences principales"),
        ("P23_MEN", "Ménages"),
        ("P23_PMEN", "Pop Ménages"),
        ("P23_RSECOCC", "Rés secondaires et logts occasionnels"),
        ("P23_LOGVAC", "Logements vacants"),
        ("P23_MAISON", "Maisons"),
        ("P23_APPART", "Appartements"),
        ("P23_RP_1P", "Rés princ 1 pièce"),
        ("P23_RP_2P", "Rés princ 2 pièces"),
        ("P23_RP_3P", "Rés princ 3 pièces"),
        ("P23_RP_4P", "Rés princ 4 pièces"),
        ("P23_RP_5PP", "Rés princ 5 pièces ou plus"),
        ("P23_RP_M30M2", "Rés princ moins de 30 m²"),
        ("P23_RP_3040M2", "Rés princ 30 à moins de 40 m²"),
        ("P23_RP_4060M2", "Rés princ 40 à moins de 60 m²"),
        ("P23_RP_6080M2", "Rés princ 60 à moins de 80 m²"),
        ("P23_RP_80100M2", "Rés princ 80 à moins de 100 m²"),
        ("P23_RP_100120M2", "Rés princ 100 à moins de 120 m²"),
        ("P23_RP_120M2P", "Rés princ 120 m² ou plus"),
        ("P23_RP_ACH1919", "Rés princ construites avant 1919"),
        ("P23_RP_ACH1945", "Rés princ construites de 1919 à 1945"),
        ("P23_RP_ACH1970", "Rés princ construites de 1946 à 1970"),
        ("P23_RP_ACH1990", "Rés princ construites de 1971 à 1990"),
        ("P23_RP_ACH2005", "Rés princ construites de 1991 à 2005"),
        ("P23_RP_ACH2019", "Rés princ construites de 2006 à 2021"),
        ("P23_MEN_ANEM0002", "Emménagement de moins de 2 ans"),
        ("P23_MEN_ANEM0204", "Emménagement de 2 à 4 ans"),
        ("P23_MEN_ANEM0509", "Emménagement de 5 à 9 ans"),
        ("P23_MEN_ANEM10P", "Emménagement de 10 ans ou plus"),
        ("P23_RP_PROP", "Propriétaires"),
        ("P23_RP_LOC", "Locataires"),
        ("P23_RP_LOCHLMV", "Locataires HLM"),
        ("P23_RP_GRAT", "Logés gratuitement"),
        ("P23_RP_VOIT1", "Ménages avec 1 voiture"),
        ("P23_RP_VOIT2P", "Ménages avec 2 voitures ou plus"),
        ("P23_RP_VOIT1P", "Ménages avec au moins 1 voiture"),
        ("P23_RP_GARL", "Ménages avec garage ou parking"),
        ("P23_RP_CGAZV", "Chauffage gaz de ville"),
        ("P23_RP_CFIOUL", "Chauffage fioul"),
        ("P23_RP_CELEC", "Chauffage électrique"),
        ("P23_RP_CGAZB", "Chauffage gaz en bouteille"),
        ("P23_RP_CAUT", "Autre chauffage"),
    ]

    for col, filt in colonnes_log.items():
        res[col] = get_val(filt)

    # Renommer les colonnes en enlevant le préfixe "P23_"
    col_mapping = {col: col.replace('P23_', '') for col in colonnes_log.keys()}
    res = res.rename(columns=col_mapping)
    # Mettre à jour les métadonnées
    meta_rows = [(col_mapping.get(col, col), lib) for col, lib in meta_rows]
    return res, meta_rows

# ==============================================================================
# 3. ACTIVITE DES RESIDENTS (ACT RES / EMP)
# ==============================================================================
def transformer_activite(df_raw, socle):
    print("Traitement du thème ACTIVITÉ DES RÉSIDENTS (ACT RES)...")
    res = socle.copy()
    iris_df = df_raw[df_raw["GEO"].astype(str).isin(res["IRIS"])]

    def get_val(filtre):
        return valeur_cube(iris_df, res, {"RP_MEASURE": "POP", **filtre})

    colonnes_act = {
        "P23_POP1564": {"AGE": "Y15T64", "SEX": "_T"},
        "P23_POP1524": {"AGE": "Y15T24", "SEX": "_T"},
        "P23_POP2554": {"AGE": "Y25T54", "SEX": "_T"},
        "P23_POP5564": {"AGE": "Y55T64", "SEX": "_T"},
        "P23_H1564": {"AGE": "Y15T64", "SEX": "M"},
        "P23_H1524": {"AGE": "Y15T24", "SEX": "M"},
        "P23_H2554": {"AGE": "Y25T54", "SEX": "M"},
        "P23_H5564": {"AGE": "Y55T64", "SEX": "M"},
        "P23_F1564": {"AGE": "Y15T64", "SEX": "F"},
        "P23_F1524": {"AGE": "Y15T24", "SEX": "F"},
        "P23_F2554": {"AGE": "Y25T54", "SEX": "F"},
        "P23_F5564": {"AGE": "Y55T64", "SEX": "F"},
        "P23_ACT1564": {"EMPSTA_ENQ": "1T2", "AGE": "Y15T64", "SEX": "_T"},
        "P23_ACT1524": {"EMPSTA_ENQ": "1T2", "AGE": "Y15T24", "SEX": "_T"},
        "P23_ACT2554": {"EMPSTA_ENQ": "1T2", "AGE": "Y25T54", "SEX": "_T"},
        "P23_ACT5564": {"EMPSTA_ENQ": "1T2", "AGE": "Y55T64", "SEX": "_T"},
        "P23_HACT1564": {"EMPSTA_ENQ": "1T2", "AGE": "Y15T64", "SEX": "M"},
        "P23_HACT1524": {"EMPSTA_ENQ": "1T2", "AGE": "Y15T24", "SEX": "M"},
        "P23_HACT2554": {"EMPSTA_ENQ": "1T2", "AGE": "Y25T54", "SEX": "M"},
        "P23_HACT5564": {"EMPSTA_ENQ": "1T2", "AGE": "Y55T64", "SEX": "M"},
        "P23_FACT1564": {"EMPSTA_ENQ": "1T2", "AGE": "Y15T64", "SEX": "F"},
        "P23_FACT1524": {"EMPSTA_ENQ": "1T2", "AGE": "Y15T24", "SEX": "F"},
        "P23_FACT2554": {"EMPSTA_ENQ": "1T2", "AGE": "Y25T54", "SEX": "F"},
        "P23_FACT5564": {"EMPSTA_ENQ": "1T2", "AGE": "Y55T64", "SEX": "F"},
        "P23_ACTOCC1564": {"EMPSTA_ENQ": "1", "AGE": "Y15T64", "SEX": "_T"},
        "P23_ACTOCC1524": {"EMPSTA_ENQ": "1", "AGE": "Y15T24", "SEX": "_T"},
        "P23_ACTOCC2554": {"EMPSTA_ENQ": "1", "AGE": "Y25T54", "SEX": "_T"},
        "P23_ACTOCC5564": {"EMPSTA_ENQ": "1", "AGE": "Y55T64", "SEX": "_T"},
        "P23_HACTOCC1564": {"EMPSTA_ENQ": "1", "AGE": "Y15T64", "SEX": "M"},
        "P23_HACTOCC1524": {"EMPSTA_ENQ": "1", "AGE": "Y15T24", "SEX": "M"},
        "P23_HACTOCC2554": {"EMPSTA_ENQ": "1", "AGE": "Y25T54", "SEX": "M"},
        "P23_HACTOCC5564": {"EMPSTA_ENQ": "1", "AGE": "Y55T64", "SEX": "M"},
        "P23_FACTOCC1564": {"EMPSTA_ENQ": "1", "AGE": "Y15T64", "SEX": "F"},
        "P23_FACTOCC1524": {"EMPSTA_ENQ": "1", "AGE": "Y15T24", "SEX": "F"},
        "P23_FACTOCC2554": {"EMPSTA_ENQ": "1", "AGE": "Y25T54", "SEX": "F"},
        "P23_FACTOCC5564": {"EMPSTA_ENQ": "1", "AGE": "Y55T64", "SEX": "F"},
        "P23_CHOM1564": {"EMPSTA_ENQ": "2", "AGE": "Y15T64", "SEX": "_T"},
        "P23_CHOM1524": {"EMPSTA_ENQ": "2", "AGE": "Y15T24", "SEX": "_T"},
        "P23_CHOM2554": {"EMPSTA_ENQ": "2", "AGE": "Y25T54", "SEX": "_T"},
        "P23_CHOM5564": {"EMPSTA_ENQ": "2", "AGE": "Y55T64", "SEX": "_T"},
        "P23_INACT1564": {"EMPSTA_ENQ": "3", "AGE": "Y15T64", "SEX": "_T"},
        "P23_ETUD1564": {"EMPSTA_ENQ": "33", "AGE": "Y15T64", "SEX": "_T"},
        "P23_RETR1564": {"EMPSTA_ENQ": "31", "AGE": "Y15T64", "SEX": "_T"},
        "P23_AINACT1564": {"EMPSTA_ENQ": "35T36", "AGE": "Y15T64", "SEX": "_T"},
    }

    meta_rows = [
        ("COM", "Commune ou ARM"),
        ("TYP_IRIS", "Type d'Iris"),
        ("LAB_IRIS", "Label de l'Iris"),
        ("P23_POP1564", "Pop 15-64 ans"),
        ("P23_POP1524", "Pop 15-24 ans"),
        ("P23_POP2554", "Pop 25-54 ans"),
        ("P23_POP5564", "Pop 55-64 ans"),
        ("P23_H1564", "Pop 15-64 ans Hommes"),
        ("P23_H1524", "Pop 15-24 ans Hommes"),
        ("P23_H2554", "Pop 25-54 ans Hommes"),
        ("P23_H5564", "Pop 55-64 ans Hommes"),
        ("P23_F1564", "Pop 15-64 ans Femmes"),
        ("P23_F1524", "Pop 15-24 ans Femmes"),
        ("P23_F2554", "Pop 25-54 ans Femmes"),
        ("P23_F5564", "Pop 55-64 ans Femmes"),
        ("P23_ACT1564", "Actifs 15-64 ans"),
        ("P23_ACT1524", "Actifs 15-24 ans"),
        ("P23_ACT2554", "Actifs 25-54 ans"),
        ("P23_ACT5564", "Actifs 55-64 ans"),
        ("P23_HACT1564", "Actifs 15-64 ans Hommes"),
        ("P23_HACT1524", "Actifs 15-24 ans Hommes"),
        ("P23_HACT2554", "Actifs 25-54 ans Hommes"),
        ("P23_HACT5564", "Actifs 55-64 ans Hommes"),
        ("P23_FACT1564", "Actifs 15-64 ans Femmes"),
        ("P23_FACT1524", "Actifs 15-24 ans Femmes"),
        ("P23_FACT2554", "Actifs 25-54 ans Femmes"),
        ("P23_FACT5564", "Actifs 55-64 ans Femmes"),
        ("P23_ACTOCC1564", "Actifs occupés 15-64 ans"),
        ("P23_ACTOCC1524", "Actifs occupés 15-24 ans"),
        ("P23_ACTOCC2554", "Actifs occupés 25-54 ans"),
        ("P23_ACTOCC5564", "Actifs occupés 55-64 ans"),
        ("P23_HACTOCC1564", "Actifs occupés 15-64 ans Hommes"),
        ("P23_HACTOCC1524", "Actifs occupés 15-24 ans Hommes"),
        ("P23_HACTOCC2554", "Actifs occupés 25-54 ans Hommes"),
        ("P23_HACTOCC5564", "Actifs occupés 55-64 ans Hommes"),
        ("P23_FACTOCC1564", "Actifs occupés 15-64 ans Femmes"),
        ("P23_FACTOCC1524", "Actifs occupés 15-24 ans Femmes"),
        ("P23_FACTOCC2554", "Actifs occupés 25-54 ans Femmes"),
        ("P23_FACTOCC5564", "Actifs occupés 55-64 ans Femmes"),
        ("P23_CHOM1564", "Chômeurs 15-64 ans"),
        ("P23_CHOM1524", "Chômeurs 15-24 ans"),
        ("P23_CHOM2554", "Chômeurs 25-54 ans"),
        ("P23_CHOM5564", "Chômeurs 55-64 ans"),
        ("P23_INACT1564", "Inactifs 15-64 ans"),
        ("P23_ETUD1564", "Élèves, étudiants 15-64 ans"),
        ("P23_RETR1564", "Retraités 15-64 ans"),
        ("P23_AINACT1564", "Autres inactifs 15-64 ans"),
    ]

    for col, filt in colonnes_act.items():
        res[col] = get_val(filt)

    # Renommer les colonnes en enlevant le préfixe "P23_"
    col_mapping = {col: col.replace('P23_', '') for col in colonnes_act.keys()}
    res = res.rename(columns=col_mapping)
    # Mettre à jour les métadonnées
    meta_rows = [(col_mapping.get(col, col), lib) for col, lib in meta_rows]
    return res, meta_rows

# ==============================================================================
# 4. COUPLES FAMILLES MENAGES (COU FAM / MEN)
# ==============================================================================
def transformer_menages(df_raw, socle, df_log_raw):
    print("Traitement du thème COUPLES, FAMILLES, MÉNAGES (COU FAM)...")
    res = socle.copy()
    iris_df = df_raw[df_raw["GEO"].astype(str).isin(res["IRIS"])]

    def get_val(filtre):
        return valeur_cube(iris_df, res, filtre)

    colonnes_men = {
        "C23_MENPSEUL": {"RP_MEASURE": "ONEPERS", "AGE": "Y_GE15"},
        "P23_POP15P_MARIEE": {"RP_MEASURE": "POP", "CIVIL_STATUS": "1", "AGE": "Y_GE15"},
        "P23_POP15P_PACSEE": {"RP_MEASURE": "POP", "CIVIL_STATUS": "2", "AGE": "Y_GE15"},
        "P23_POP15P_CONCUB_UNION_LIBRE": {"RP_MEASURE": "POP", "CIVIL_STATUS": "3", "AGE": "Y_GE15"},
        "P23_POP15P_VEUFS": {"RP_MEASURE": "POP", "CIVIL_STATUS": "4", "AGE": "Y_GE15"},
        "P23_POP15P_DIVORCEE": {"RP_MEASURE": "POP", "CIVIL_STATUS": "5", "AGE": "Y_GE15"},
        "P23_POP15P_CELIBATAIRE": {"RP_MEASURE": "POP", "CIVIL_STATUS": "6", "AGE": "Y_GE15"},
    }

    meta_rows = [
        ("COM", "Commune ou ARM"),
        ("TYP_IRIS", "Type d'Iris"),
        ("LAB_IRIS", "Label de l'Iris"),
        ("C23_MEN", "Ménages"),
        ("C23_MENPSEUL", "Ménages 1 personne"),
        ("P23_POP15P_MARIEE", "Pop 15 ans ou plus Mariée"),
        ("P23_POP15P_PACSEE", "Pop 15 ans ou plus Pacsée"),
        ("P23_POP15P_CONCUB_UNION_LIBRE", "Pop 15 ans ou plus Concubinage"),
        ("P23_POP15P_VEUFS", "Pop 15 ans ou plus Veufs"),
        ("P23_POP15P_DIVORCEE", "Pop 15 ans ou plus Divorcée"),
        ("P23_POP15P_CELIBATAIRE", "Pop 15 ans ou plus Célibataire"),
    ]

    # Le cube MEN n'a pas de mesure "ménages" : ménages = résidences principales (cube LOG)
    iris_log = df_log_raw[df_log_raw["GEO"].astype(str).isin(res["IRIS"])]
    res["C23_MEN"] = valeur_cube(iris_log, res, {"RP_MEASURE": "DWELLINGS", "OCS": "DW_MAIN"})
    for col, filt in colonnes_men.items():
        res[col] = get_val(filt)

    # Renommer les colonnes en enlevant le préfixe "P23_"
    col_mapping = {col: col.replace('P23_', '') for col in ["C23_MEN", *colonnes_men.keys()]}
    res = res.rename(columns=col_mapping)
    # Mettre à jour les métadonnées
    meta_rows = [(col_mapping.get(col, col), lib) for col, lib in meta_rows]
    return res, meta_rows

# ==============================================================================
# 5. DIPLOMES ET FORMATION (DIP FORMATION / DIP)
# ==============================================================================
def transformer_diplomes(df_raw, socle):
    print("Traitement du thème DIPLÔMES ET FORMATION (DIP FORMATION)...")
    res = socle.copy()
    iris_df = df_raw[df_raw["GEO"].astype(str).isin(res["IRIS"])]

    def get_val(filtre):
        return valeur_cube(iris_df, res, {"RP_MEASURE": "POP", **filtre})

    colonnes_dip = {
        "P23_NSCOL15P": {"AGE": "Y_GE15", "EDUC": "_T", "SEX": "_T"},
        "P23_NSCOL15P_DIPLMIN": {"AGE": "Y_GE15", "EDUC": "001T100_RP", "SEX": "_T"},
        "P23_NSCOL15P_BEPC": {"AGE": "Y_GE15", "EDUC": "200_RP", "SEX": "_T"},
        "P23_NSCOL15P_CAPBEP": {"AGE": "Y_GE15", "EDUC": "300_RP", "SEX": "_T"},
        "P23_NSCOL15P_BAC": {"AGE": "Y_GE15", "EDUC": "350T351_RP", "SEX": "_T"},
        "P23_NSCOL15P_SUP2": {"AGE": "Y_GE15", "EDUC": "500_RP", "SEX": "_T"},
        "P23_NSCOL15P_SUP34": {"AGE": "Y_GE15", "EDUC": "600_RP", "SEX": "_T"},
        "P23_NSCOL15P_SUP5": {"AGE": "Y_GE15", "EDUC": "700_RP", "SEX": "_T"},
        "P23_HNSCOL15P": {"AGE": "Y_GE15", "EDUC": "_T", "SEX": "M"},
        "P23_HNSCOL15P_DIPLMIN": {"AGE": "Y_GE15", "EDUC": "001T100_RP", "SEX": "M"},
        "P23_HNSCOL15P_CAPBEP": {"AGE": "Y_GE15", "EDUC": "300_RP", "SEX": "M"},
        "P23_HNSCOL15P_BAC": {"AGE": "Y_GE15", "EDUC": "350T351_RP", "SEX": "M"},
        "P23_FNSCOL15P": {"AGE": "Y_GE15", "EDUC": "_T", "SEX": "F"},
        "P23_FNSCOL15P_DIPLMIN": {"AGE": "Y_GE15", "EDUC": "001T100_RP", "SEX": "F"},
        "P23_FNSCOL15P_CAPBEP": {"AGE": "Y_GE15", "EDUC": "300_RP", "SEX": "F"},
        "P23_FNSCOL15P_BAC": {"AGE": "Y_GE15", "EDUC": "350T351_RP", "SEX": "F"},
    }

    meta_rows = [
        ("COM", "Commune ou ARM"),
        ("TYP_IRIS", "Type d'Iris"),
        ("LAB_IRIS", "Label de l'Iris"),
        ("P23_NSCOL15P", "Pop non scolarisée 15 ans ou plus"),
        ("P23_NSCOL15P_DIPLMIN", "Pop non scol 15 ans ou plus Aucun diplôme ou CEP"),
        ("P23_NSCOL15P_BEPC", "Pop non scol 15 ans ou plus Brevet des collèges"),
        ("P23_NSCOL15P_CAPBEP", "Pop non scol 15 ans ou plus CAP, BEP"),
        ("P23_NSCOL15P_BAC", "Pop non scol 15 ans ou plus Baccalauréat"),
        ("P23_NSCOL15P_SUP2", "Pop non scol 15 ans ou plus Enseignement court Bac+2"),
        ("P23_NSCOL15P_SUP34", "Pop non scol 15 ans ou plus Bac+3 ou Bac+4"),
        ("P23_NSCOL15P_SUP5", "Pop non scol 15 ans ou plus Bac+5 ou plus"),
        ("P23_HNSCOL15P", "Pop non scolarisée 15 ans ou plus Hommes"),
        ("P23_HNSCOL15P_DIPLMIN", "Pop non scol 15P Hommes Aucun diplôme ou CEP"),
        ("P23_HNSCOL15P_CAPBEP", "Pop non scol 15P Hommes CAP, BEP"),
        ("P23_HNSCOL15P_BAC", "Pop non scol 15P Hommes Baccalauréat"),
        ("P23_FNSCOL15P", "Pop non scolarisée 15 ans ou plus Femmes"),
        ("P23_FNSCOL15P_DIPLMIN", "Pop non scol 15P Femmes Aucun diplôme ou CEP"),
        ("P23_FNSCOL15P_CAPBEP", "Pop non scol 15P Femmes CAP, BEP"),
        ("P23_FNSCOL15P_BAC", "Pop non scol 15P Femmes Baccalauréat"),
    ]

    for col, filt in colonnes_dip.items():
        res[col] = get_val(filt)

    # Renommer les colonnes en enlevant le préfixe "P23_"
    col_mapping = {col: col.replace('P23_', '') for col in colonnes_dip.keys()}
    res = res.rename(columns=col_mapping)
    # Mettre à jour les métadonnées
    meta_rows = [(col_mapping.get(col, col), lib) for col, lib in meta_rows]
    return res, meta_rows

# ==============================================================================
# 6. FICHIERS COMPLÉMENTAIRES (DS_RP_…_IRIS_AAAA)
# ==============================================================================
# Cubes Insee publiés à part des 5 cubes principaux, déposés sous leur nom Insee
# dans data/dataAAAA/complementaires/. Ils rendent les colonnes du modèle 2022 que les
# cubes principaux n'ont pas. Chaque fichier est facultatif : absent, ses colonnes
# ne sont pas produites. Les codes reprennent ceux du fichier 2022 (préfixe 23,
# même ordre) pour que l'ingestion retrouve les en-têtes du modèle.

# Code PCS du cube -> suffixe GSEC des codes 2022
GSEC_POP = {"1": "11_21", "2": "12_22", "3": "13_23", "4": "14_24", "5": "15_25", "6": "16_26", "7": "32", "9": "40"}
GSEC_ACT = {"1": "11_21", "2": "12_22", "3": "13_23", "4": "14_24", "5": "15_25", "6": "16_26"}
LIBELLES_PCS = {
    "1": "Agriculteurs exploitants", "2": "Artisans, Comm., Chefs entr.", "3": "Cadres, Prof. intel. sup.",
    "4": "Prof. intermédiaires", "5": "Employés", "6": "Ouvriers", "7": "Retraités", "9": "Autres",
}
LIBELLES_PCS_MEN = {
    "1": "Agri. expl.", "2": "Art. Comm. Chef entr.", "3": "Cadre Prof int sup", "4": "Prof intermédiaire",
    "5": "Employé", "6": "Ouvrier", "7": "Retraité", "9": "Autre",
}


def _colonnes_pop_comp():
    colonnes = []
    for prefixe, sexe, libelle in [("POP15P", "_T", ""), ("H15P", "M", " Hommes"), ("F15P", "F", " Femmes")]:
        colonnes.append((f"C23_{prefixe}", {"SEX": sexe, "PCS": "_T"}, f"Pop 15 ans ou plus{libelle}"))
        for pcs, gsec in GSEC_POP.items():
            colonnes.append((
                f"C23_{prefixe}_STAT_GSEC{gsec}", {"SEX": sexe, "PCS": pcs},
                f"Pop 15 ans ou plus{libelle} {LIBELLES_PCS[pcs]}",
            ))
    return colonnes


def _colonnes_emploi_comp():
    colonnes = []
    for prefixe, statut, libelle in [("ACT1564", "1T2", "Actifs 15-64 ans"), ("ACTOCC1564", "1", "Actifs occ 15-64 ans")]:
        for pcs, gsec in GSEC_ACT.items():
            # 2022 : GSEC11_21 pour les actifs, GSEC11 pour les actifs occupés
            suffixe = gsec if statut == "1T2" else gsec.split("_")[0]
            colonnes.append((
                f"C23_{prefixe}_STAT_GSEC{suffixe}", {"EMPSTA_ENQ": statut, "PCS": pcs},
                f"{libelle} {LIBELLES_PCS[pcs]}",
            ))
    return colonnes


def _colonnes_menages_comp():
    # TPH : 11 personnes seules (110 hommes, 111 femmes), 12 autres sans famille, 2 avec famille(s),
    # familles principales MF221 couple sans enfant, MF222 couple avec enfant(s), MF21 monoparentale
    # (vérifié sur la taille moyenne des ménages et les totaux 2022)
    types = [
        ("MENHSEUL", "110", "Ménages Hommes seuls", "Hommes seuls"),
        ("MENFSEUL", "111", "Ménages Femmes seules", "Femmes seules"),
        ("MENSFAM", "12", "Ménages Autres sans famille", "Autres sans famille"),
        ("MENFAM", "2", "Ménages avec famille(s)", "avec famille(s)"),
        ("MENCOUPSENF", "MF221", "Mén fam princ Couple sans enfant", "fam princ Couple sans enfant"),
        ("MENCOUPAENF", "MF222", "Mén fam princ Couple avec enfant(s)", "fam princ Couple avec enfant(s)"),
        ("MENFAMMONO", "MF21", "Mén fam princ Famille mono", "fam princ Famille mono"),
    ]
    menages = {"RP_MEASURE": "DWELLINGS"}
    population = {"RP_MEASURE": "DWELLINGS_POPSIZE"}
    colonnes = [(f"C23_{code}", {**menages, "TPH": tph}, libelle) for code, tph, libelle, _ in types]
    colonnes.append(("C23_PMEN", {**population, "TPH": "_T", "PCS": "_T"}, "Pop Ménages"))
    colonnes.append(("C23_PMEN_MENPSEUL", {**population, "TPH": "11"}, "Pop mén Personnes seules"))
    colonnes += [(f"C23_PMEN_{code}", {**population, "TPH": tph}, f"Pop mén {libelle}") for code, tph, _, libelle in types]
    for prefixe, mesure, libelle in [("MEN", menages, "Ménages"), ("PMEN", population, "Pop mén")]:
        colonnes += [
            (f"C23_{prefixe}_STAT_GSEC{gsec}", {**mesure, "TPH": "_T", "PCS": pcs}, f"{libelle} Pers Réf {LIBELLES_PCS_MEN[pcs]}")
            for pcs, gsec in GSEC_POP.items()
        ]
    return colonnes


def _colonnes_famille_comp():
    # TFN : 1 monoparentale, 21 couple sans enfant, 22 couple avec enfant(s),
    # 223 uniquement enfants du couple, 220 au moins un enfant d'un seul des deux
    colonnes = [
        ("C23_FAM", {"TFN": "_T", "NCH": "_T"}, "Familles"),
        ("C23_COUPAENF", {"TFN": "22"}, "Fam Couple avec enfant(s)"),
        ("C23_FAMMONO", {"TFN": "1"}, "Fam Monoparentales"),
        ("C23_COUPSENF", {"TFN": "21"}, "Fam Couple sans enfant"),
    ]
    for code, nch, libelle in [
        ("NE24F0", "CH0_Y_LT25", "0 enfant"), ("NE24F1", "CH1_Y_LT25", "1 enfant"),
        ("NE24F2", "CH2_Y_LT25", "2 enfants"), ("NE24F3", "CH3_Y_LT25", "3 enfants"),
        ("NE24F4P", "CH_GE4_Y_LT25", "4 enfants ou plus"),
    ]:
        colonnes.append((f"C23_{code}", {"NCH": nch}, f"Fam {libelle} moins 25 ans"))
    colonnes += [
        ("C23_FAMTRAD", {"TFN": "223"}, "Fam Couple avec uniquement enfant(s) du couple"),
        ("C23_FAMRECOMP", {"TFN": "220"}, "Fam Couple avec au moins un enfant d'un seul des 2 membres du couple"),
    ]
    return [(code, {"RP_MEASURE": "NBFAM", **filtre}, libelle) for code, filtre, libelle in colonnes]


def _colonnes_activite_princ():
    colonnes = []
    for code, sexe, forme, temps, libelle in [
        ("ACTOCC15P", "_T", "_T", "_T", "Actifs occupés 15 ans ou plus"),
        ("HACTOCC15P", "M", "_T", "_T", "Actifs occupés 15 ans ou plus Hommes"),
        ("FACTOCC15P", "F", "_T", "_T", "Actifs occupés 15 ans ou plus Femmes"),
        ("SAL15P", "_T", "2", "_T", "Salariés 15 ans ou plus"),
        ("HSAL15P", "M", "2", "_T", "Salariés 15 ans ou plus Hommes"),
        ("FSAL15P", "F", "2", "_T", "Salariés 15 ans ou plus Femmes"),
        ("NSAL15P", "_T", "1", "_T", "Non-salariés 15 ans ou plus"),
        ("HNSAL15P", "M", "1", "_T", "Non-salariés 15 ans ou plus Hommes"),
        ("FNSAL15P", "F", "1", "_T", "Non-salariés 15 ans ou plus Femmes"),
        ("ACTOCC15P_TP", "_T", "_T", "PT", "Actifs occ 15 ans ou plus TP"),
        ("SAL15P_TP", "_T", "2", "PT", "Salariés 15 ans ou plus TP"),
        ("HSAL15P_TP", "M", "2", "PT", "Salariés 15 ans ou plus TP Hommes"),
        ("FSAL15P_TP", "F", "2", "PT", "Salariés 15 ans ou plus TP Femmes"),
        ("NSAL15P_TP", "_T", "1", "PT", "Non-salariés 15 ans ou plus TP"),
        # Le cube ne détaille pas CDD, intérim, emplois aidés, apprentissage (regroupés en 22T27)
        ("SAL15P_CDI", "_T", "211", "_T", "Salariés 15 ans ou plus Fonct publ, CDI"),
    ]:
        colonnes.append((
            f"P23_{code}",
            {"RP_MEASURE": "POP", "EMPSTA_ENQ": "1", "SEX": sexe, "EMPFORM": forme, "WKTIME": temps},
            libelle,
        ))
    return colonnes


def _colonnes_navettes_princ():
    colonnes = [
        (f"P23_ACTOCC15P_{code}", {"WORK_AREA": zone, "TRANS": "_T"}, f"Actif occ 15 ans ou plus travaille {libelle}")
        for code, zone, libelle in [
            ("ILT1", "10", "commune résidence"),
            ("ILT2P", "20_30", "autre commune que commune résidence"),
            ("ILT2", "21", "autre commune même dépt résidence"),
            ("ILT3", "22", "autre dépt même région résidence"),
            ("ILT4", "23", "autre région en métropole"),
            ("ILT5", "24T30", "autre région hors métropole"),
        ]
    ]
    colonnes.append(("C23_ACTOCC15P", {"WORK_AREA": "_T", "TRANS": "_T"}, "Actif occ 15 ans ou plus"))
    colonnes += [
        (f"C23_ACTOCC15P_{code}", {"WORK_AREA": "_T", "TRANS": mode}, f"Actifs occ 15 ans ou plus {libelle}")
        for code, mode, libelle in [
            ("PAS", "1", "pas de transport pour travail"),
            ("MAR", "2", "marche à pied pour travail"),
            ("VELO", "3", "vélo"),
            ("2ROUESMOT", "4", "deux-roues motorisé"),
            ("VOIT", "5", "voiture"),
            ("TCOM", "6", "transport en commun"),
        ]
    ]
    return [(code, {"RP_MEASURE": "POP", "EMPSTA_ENQ": "1", **filtre}, libelle) for code, filtre, libelle in colonnes]


def _colonnes_education_princ():
    tranches = [
        ("0205", "Y2T5", "2-5 ans"), ("0610", "Y6T10", "6-10 ans"), ("1114", "Y11T14", "11-14 ans"),
        ("1517", "Y15T17", "15-17 ans"), ("1824", "Y18T24", "18-24 ans"), ("2529", "Y25T29", "25-29 ans"),
        ("30P", "Y_GE30", "30 ans ou plus"),
    ]
    colonnes = [(f"P23_POP{code}", {"AGE": age, "STUD": "_T"}, f"Pop {libelle}") for code, age, libelle in tranches]
    colonnes += [(f"P23_SCOL{code}", {"AGE": age, "STUD": "1"}, f"Pop scolarisée {libelle}") for code, age, libelle in tranches]
    return [(code, {"RP_MEASURE": "POP", **filtre}, libelle) for code, filtre, libelle in colonnes]


def _colonnes_logement_comp():
    return [
        (f"C23_RP_{code}", {"RP_MEASURE": "DWELLINGS", "OCS": "DW_MAIN", "OCC_IND": occupation}, f"Rés princ {libelle}")
        for code, occupation, libelle in [
            ("NORME", "STD_OCC", "occupation norme"),
            ("SOUSOCC_MOD", "MOD_UNDER_OCC", "sous-occupation modérée"),
            ("SOUSOCC_ACC", "SEV_UNDER_OCC", "sous-occupation accentuée"),
            ("SOUSOCC_TACC", "VSEV_UNDER_OCC", "sous-occupation très accentuée"),
            ("SUROCC_MOD", "MOD_OVER_OCC", "suroccupation modérée"),
            ("SUROCC_ACC", "SEV_OVER_OCC", "suroccupation accentuée"),
        ]
    ]


# Thème produit -> fichiers complémentaires (nom Insee sans _IRIS_AAAA), dans l'ordre des colonnes 2022
COMPLEMENTAIRES = {
    "pop": [("DS_RP_POPULATION_COMP", _colonnes_pop_comp)],
    "emp": [
        ("DS_RP_EMPLOI_LR_COMP", _colonnes_emploi_comp),
        ("DS_RP_ACTIVITE_PRINC", _colonnes_activite_princ),
        ("DS_RP_NAVETTES_PRINC", _colonnes_navettes_princ),
    ],
    "men": [("DS_RP_MENAGES_COMP", _colonnes_menages_comp), ("DS_RP_FAMILLE_COMP", _colonnes_famille_comp)],
    "dip": [("DS_RP_EDUCATION_PRINC", _colonnes_education_princ)],
    "log": [("DS_RP_LOGEMENT_COMP", _colonnes_logement_comp)],
}


def dossier_complementaires(annee):
    return os.path.join(DOSSIER_DATA, f"data{annee}", "complementaires")


def chemin_complementaire(nom, annee):
    """Fichier DS_RP_…_IRIS_AAAA (.parquet préféré, sinon .csv) ; None s'il n'a pas été déposé."""
    dossier = dossier_complementaires(annee)
    if not os.path.isdir(dossier):
        return None
    fichiers = {f.casefold(): os.path.join(dossier, f) for f in os.listdir(dossier)}
    for extension in (".parquet", ".csv"):
        chemin = fichiers.get(f"{nom}_IRIS_{annee}{extension}".casefold())
        if chemin:
            return chemin
    return None


def ajouter_complementaires(theme, res, meta_rows, annee):
    """Ajoute à la table du thème les colonnes des fichiers complémentaires présents."""
    for nom, colonnes in COMPLEMENTAIRES[theme]:
        chemin = chemin_complementaire(nom, annee)
        if not chemin:
            print(f"  -> {nom}_IRIS_{annee} absent de {dossier_complementaires(annee)} : colonnes non produites")
            continue
        df_raw = charger_roubaix(chemin)
        iris_df = df_raw[df_raw["GEO"].astype(str).isin(res["IRIS"])]
        nouvelles = {code: valeur_cube(iris_df, res, filtre) for code, filtre, _ in colonnes()}
        res = pd.concat([res.drop(columns=list(nouvelles), errors="ignore"), pd.DataFrame(nouvelles)], axis=1)
        meta_rows = meta_rows + [(code, libelle) for code, _, libelle in colonnes()]
    return res, meta_rows


def transformer_millesime(annee, force=False):
    if not force and sorties_a_jour(annee):
        print(f"=== Fichiers Insee {annee} déjà transformés et à jour : rien à refaire ===")
        print("  (pour tout recalculer : python scripts/transformer_recensement.py --force)")
        return
    print(f"=== Démarrage de la transformation Insee {annee} pour Roubaix ===")
    manquants = [
        theme for theme in THEMES_SOURCES
        if not os.path.exists(chemin_source(theme, annee))
    ]
    if manquants:
        raise FileNotFoundError(
            f"Cubes {annee} manquants dans {dossier_sources(annee)} : "
            + ", ".join(f"base-ic-{theme}-{annee}" for theme in manquants)
        )

    # 1. Chargement de POP pour initialiser le socle géographique
    fichier_pop = chemin_source("pop", annee)
    df_pop_raw = charger_roubaix(fichier_pop)
    socle = extraire_socle_geo(df_pop_raw)
    print(f"Socle géographique : {len(socle)} IRIS trouvés pour Roubaix.")

    # 1. POP
    df_pop, meta_pop = transformer_population(df_pop_raw, socle)
    df_pop, meta_pop = ajouter_complementaires("pop", df_pop, meta_pop, annee)
    
    # 2. LOG
    fichier_log = chemin_source("log", annee)
    df_log_raw = charger_roubaix(fichier_log)
    df_log, meta_log = transformer_logement(df_log_raw, socle)
    df_log, meta_log = ajouter_complementaires("log", df_log, meta_log, annee)

    # 3. EMP
    fichier_emp = chemin_source("emp", annee)
    df_emp_raw = charger_roubaix(fichier_emp)
    df_emp, meta_emp = transformer_activite(df_emp_raw, socle)
    df_emp, meta_emp = ajouter_complementaires("emp", df_emp, meta_emp, annee)

    # 4. MEN
    fichier_men = chemin_source("men", annee)
    df_men_raw = charger_roubaix(fichier_men)
    df_men, meta_men = transformer_menages(df_men_raw, socle, df_log_raw)
    df_men, meta_men = ajouter_complementaires("men", df_men, meta_men, annee)

    # 5. DIP
    fichier_dip = chemin_source("dip", annee)
    df_dip_raw = charger_roubaix(fichier_dip)
    df_dip, meta_dip = transformer_diplomes(df_dip_raw, socle)
    df_dip, meta_dip = ajouter_complementaires("dip", df_dip, meta_dip, annee)

    # Sauvegardes (même ordre que BASES_SORTIES)
    sorties = [
        (nom_data, df_res, nom_meta, meta_tuples)
        for (nom_data, nom_meta), (df_res, meta_tuples) in zip(
            noms_sorties(annee),
            [(df_pop, meta_pop), (df_log, meta_log), (df_emp, meta_emp), (df_men, meta_men), (df_dip, meta_dip)],
        )
    ]

    print("\n=== Contrôle de cohérence (somme Roubaix) ===")
    for libelle, valeur in [
        ("Population", df_pop["POP"].sum()),
        ("Pop Hommes + Femmes", df_pop["POPH"].sum() + df_pop["POPF"].sum()),
        ("Pop Français + Etrangers", df_pop["POP_FR"].sum() + df_pop["POP_ETR"].sum()),
        ("Logements", df_log["LOG"].sum()),
        ("RP + RSECOCC + LOGVAC", df_log["RP"].sum() + df_log["RSECOCC"].sum() + df_log["LOGVAC"].sum()),
        ("Résidences principales", df_log["RP"].sum()),
        ("RP 1 à 5+ pièces", sum(df_log[c].sum() for c in ["RP_1P", "RP_2P", "RP_3P", "RP_4P", "RP_5PP"])),
        ("Ménages (COU FAM)", df_men["C23_MEN"].sum()),
        ("Ménages 1 personne", df_men["C23_MENPSEUL"].sum()),
        ("Pop 15-64 ans", df_emp["POP1564"].sum()),
        ("Actifs + Inactifs 15-64", df_emp["ACT1564"].sum() + df_emp["INACT1564"].sum()),
        ("Pop non scol 15+", df_dip["NSCOL15P"].sum()),
    ] + [
        # Fichiers complémentaires, quand ils sont présents
        (libelle, valeur())
        for libelle, colonnes, valeur in [
            ("Pop 15+ par CSP (POP15P)", ["C23_POP15P"], lambda: df_pop["C23_POP15P"].sum()),
            ("Ménages par type", ["C23_MENFAM"], lambda: sum(
                df_men[c].sum() for c in ["C23_MENHSEUL", "C23_MENFSEUL", "C23_MENSFAM", "C23_MENFAM"]
            )),
            ("Familles", ["C23_FAM"], lambda: df_men["C23_FAM"].sum()),
            ("Familles par type", ["C23_COUPAENF"], lambda: sum(
                df_men[c].sum() for c in ["C23_COUPAENF", "C23_FAMMONO", "C23_COUPSENF"]
            )),
            ("Actifs occupés 15+", ["P23_ACTOCC15P"], lambda: df_emp["P23_ACTOCC15P"].sum()),
            ("Salariés + Non-salariés", ["P23_SAL15P"], lambda: df_emp["P23_SAL15P"].sum() + df_emp["P23_NSAL15P"].sum()),
            ("Actifs occ. commune + autre", ["P23_ACTOCC15P_ILT1"], lambda: df_emp["P23_ACTOCC15P_ILT1"].sum() + df_emp["P23_ACTOCC15P_ILT2P"].sum()),
        ]
        if all(colonne in (df_pop.columns.tolist() + df_men.columns.tolist() + df_emp.columns.tolist()) for colonne in colonnes)
    ]:
        print(f"  {libelle:<28} {valeur:>12,.0f}")
    if df_pop["POP"].sum() == 0:
        # Codes de dimensions changés par l'Insee : aucun filtre ne trouve de ligne
        raise ValueError(
            f"Population nulle pour {annee} : les dimensions des cubes ont probablement changé "
            "(voir doc/nouveau_millesime.md)."
        )
    colonnes_nulles = [
        avec_millesime(colonne, annee)
        for _, df_res, _, _ in sorties
        for colonne in df_res.columns
        if colonne not in {"IRIS", "COM", "TYP_IRIS", "LAB_IRIS"}
        and pd.api.types.is_numeric_dtype(df_res[colonne]) and df_res[colonne].sum() == 0
    ]
    if colonnes_nulles:
        print(f"\n  [À VÉRIFIER] Colonnes à 0 sur tout Roubaix : {', '.join(colonnes_nulles)}")

    print("\n=== Écriture des fichiers de données et métadonnées ===")
    os.makedirs(dossier_sortie_data(annee), exist_ok=True)
    os.makedirs(dossier_sortie_meta(annee), exist_ok=True)
    for nom_csv, df_res, nom_meta, meta_tuples in sorties:
        # Codes au préfixe du millésime (P23_ -> P24_…) ; sans effet pour 2023
        df_res = df_res.rename(columns=lambda colonne: avec_millesime(colonne, annee))
        meta_tuples = [(avec_millesime(code, annee), libelle) for code, libelle in meta_tuples]
        # Données CSV
        path_csv = os.path.join(dossier_sortie_data(annee), nom_csv)
        try:
            df_res.to_csv(path_csv, sep=";", index=False, encoding="utf-8-sig")
            taille_ko = os.path.getsize(path_csv) / 1024
            print(f"  [DATA] {nom_csv} ({len(df_res)} lignes, {len(df_res.columns)} colonnes, {taille_ko:.1f} Ko)")
        except PermissionError:
            print(f"  [ERREUR] Impossible d'écrire {nom_csv} : le fichier est probablement ouvert dans Excel !")
            raise

        # Méta CSV
        path_meta = os.path.join(dossier_sortie_meta(annee), nom_meta)
        df_meta = pd.DataFrame(meta_tuples, columns=["COD_VAR", "LIB_VAR"])
        df_meta.to_csv(path_meta, sep=";", index=False, encoding="utf-8-sig")
        print(f"  [META] {nom_meta} ({len(df_meta)} variables documentees)")

    print("\n=== Terminé avec succès ! ===")


def main():
    parser = argparse.ArgumentParser(description="Conversion des cubes Insee du recensement pour Roubaix.")
    parser.add_argument("--annee", help="millésime à traiter (par défaut : tous ceux présents dans data/)")
    parser.add_argument("--force", action="store_true", help="recalcule même si les fichiers produits sont à jour")
    arguments = parser.parse_args()

    annees = [arguments.annee] if arguments.annee else millesimes_disponibles()
    if not annees:
        print("Aucun cube brut dans data/dataAAAA/sources_brutes_insee/ : rien à transformer.")
        return
    for annee in annees:
        transformer_millesime(annee, force=arguments.force)
        print()

if __name__ == "__main__":
    main()
