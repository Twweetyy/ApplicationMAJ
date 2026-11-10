"""Périmètre MEL de la base MAS : une ligne par commune de la Métropole Européenne de Lille.

Les sources restent lues à l'IRIS, filtrées sur les 95 communes de communes_mel.yml, puis
additionnées par commune (code commune = 5 premiers caractères du code IRIS) avant le calcul
des indicateurs : un taux MEL ou communal est donc toujours une somme divisée par une somme.

- Les effectifs (colonnes additives) sont sommés.
- Les valeurs non additives des sources (taux RPLS, loyers moyens, médianes…) ne peuvent pas
  être reconstituées par somme : elles sont retirées de l'onglet.
- Une commune absente d'une source (CAF, CNAM, DEFM et RPLS ne couvrent que les communes
  découpées en IRIS) reste vide dans l'onglet de cette source, indicateurs compris.
"""
import os
import re

import pandas as pd

from .ingestion import load_mapping

PERIMETRES = {"roubaix": "Roubaix", "mel": "MEL"}
CODE_ROUBAIX = "59512"
CODE_EPCI_MEL = "200093201"
COLONNE_CODE = "Code Insee"
COLONNE_COMMUNE = "Commune"
# Colonnes grises du modèle réutilisées pour le code et le nom de la commune ; les autres
# colonnes de zonage (quartiers de Roubaix) sont absentes des données et retirées à l'export.
RENOMMAGES_ZONAGE_MEL = {
    "Grands quartiers": COLONNE_CODE,
    "Quartiers SIG (Grands quartiers)": COLONNE_CODE,
    "Libellé de l'Iris": COLONNE_COMMUNE,
}
COLONNES_TECHNIQUES = {"iris", "com", "codgeo", "typiris", "labiris", "note", "depcom", "libcom"}


def _normaliser(nom) -> str:
    return re.sub(r"[^a-z0-9]", "", str(nom).casefold())


def charger_communes_mel(dossier_dicos: str) -> dict[str, str]:
    """{code Insee: nom} des communes de la MEL, dans l'ordre de communes_mel.yml."""
    communes = load_mapping(os.path.join(dossier_dicos, "communes_mel.yml"))
    return {str(code).strip(): str(nom) for code, nom in communes.items()}


def codes_communes(perimetre: str, dossier_dicos: str) -> set[str]:
    """Codes commune retenus par le filtre d'ingestion pour ce périmètre."""
    if perimetre == "mel":
        return set(charger_communes_mel(dossier_dicos))
    return {CODE_ROUBAIX}


def _colonne_additive(nom_colonne: str, nom_table: str) -> bool:
    from .indicateurs import _precision_arrondi
    from .mise_en_page import _est_additive

    precision = _precision_arrondi(str(nom_colonne), nom_table)
    if precision is None:
        return False
    return _est_additive(str(nom_colonne), nom_table, precision)


def agreger_par_commune(dico_fichiers: dict, communes: dict[str, str]) -> tuple[dict, dict]:
    """Somme les tables IRIS par commune ; retourne les tables et, par table, les communes présentes.

    Toutes les tables ont les mêmes lignes, dans le même ordre (celui de communes_mel.yml) :
    les indicateurs qui lisent une colonne d'un autre onglet (ex. Population de POP dans CAF)
    restent alignés ligne à ligne.
    """
    index = pd.Index(list(communes), name=COLONNE_CODE)
    resultat, presences = {}, {}
    for nom_table, dataframe in dico_fichiers.items():
        if dataframe is None or "IRIS" not in dataframe.columns:
            resultat[nom_table] = dataframe
            continue
        codes = dataframe["IRIS"].astype("string").str.strip().str[:5]
        colonnes = [
            colonne
            for colonne in dataframe.columns
            if _normaliser(colonne) not in COLONNES_TECHNIQUES and _colonne_additive(colonne, nom_table)
        ]
        valeurs = dataframe[colonnes].apply(
            lambda serie: pd.to_numeric(serie.astype("string").str.replace(",", ".", regex=False), errors="coerce")
        )
        sommes = valeurs.groupby(codes.values).sum(min_count=1).reindex(index)
        presences[nom_table] = set(codes.dropna()) & set(communes)
        sommes.insert(0, COLONNE_COMMUNE, [communes[code] for code in index])
        resultat[nom_table] = sommes.reset_index()
    return resultat, presences


def vider_communes_absentes(dico_fichiers: dict, presences: dict) -> dict:
    """Après calcul des indicateurs : une commune absente d'une source n'a aucune valeur dans son onglet.

    Sans ça, les colonnes recopiées d'un autre onglet (Population (CAF)…) seraient remplies et
    fausseraient le total MEL des taux.
    """
    for nom_table, presentes in presences.items():
        dataframe = dico_fichiers.get(nom_table)
        if dataframe is None or COLONNE_CODE not in dataframe.columns:
            continue
        absentes = ~dataframe[COLONNE_CODE].isin(presentes)
        if not absentes.any():
            continue
        colonnes = [colonne for colonne in dataframe.columns if colonne not in {COLONNE_CODE, COLONNE_COMMUNE}]
        dataframe = dataframe.copy()
        for colonne in colonnes:
            if pd.api.types.is_numeric_dtype(dataframe[colonne]):
                dataframe[colonne] = dataframe[colonne].astype("float64")
            dataframe.loc[absentes, colonne] = pd.NA
        dico_fichiers[nom_table] = dataframe
    return dico_fichiers


# Textes de la page Présentation (modèle écrit pour Roubaix) : (motif, remplacement)
REMPLACEMENTS_PRESENTATION = [
    (r"de Roubaix", "des communes de la MEL"),
    (r"à l'Iris", "à la commune (somme des IRIS)"),
    (r"# Les données INSEE\s+sont à\s+l'échelle des IRIS",
     "# Les données sont présentées à l'échelle communale : les 95 communes de la Métropole Européenne de Lille"),
    (r"^Dans les onglets, chaque iris.*",
     "Chaque ligne est une commune : ses effectifs sont la somme de ses IRIS, et les taux sont recalculés "
     "à partir de ces sommes (jamais une moyenne de taux). La ligne Total donne la MEL.\n"
     "CAF, CNAM, DEFM et RPLS ne sont diffusés que pour les communes découpées en IRIS : les autres communes "
     "restent vides dans ces onglets, et les valeurs soumises au secret statistique ne sont pas comptées. "
     "Les taux et loyers moyens du RPLS, non additifs, ne sont pas repris ; sans superficie communale, "
     "les densités ne sont pas calculées.\n"
     "Des indicateurs supplémentaires calculés sont disponibles à la fin des feuilles (tout à droite) sous fond orange"),
    (r"COM-59512", f"EPCI-{CODE_EPCI_MEL}"),
    (r"l'échelle de la commune", "l'échelle de la métropole"),
]


def adapter_presentation_mel(workbook) -> None:
    """Réécrit les textes propres à Roubaix de la page Présentation pour le périmètre MEL."""
    if "Présentation" not in workbook.sheetnames:
        return
    ws = workbook["Présentation"]
    for ligne in ws.iter_rows():
        for cellule in ligne:
            if not isinstance(cellule.value, str):
                continue
            texte = cellule.value
            for motif, remplacement in REMPLACEMENTS_PRESENTATION:
                drapeaux = (re.MULTILINE | re.DOTALL) if motif.startswith("^") else 0
                texte = re.sub(motif, remplacement, texte, flags=drapeaux)
            if texte != cellule.value:
                if texte.count("\n") > cellule.value.count("\n"):
                    # Texte de précision plus long : hauteur de ligne agrandie (Excel ne la recalcule pas)
                    hauteur = ws.row_dimensions[cellule.row].height or 15
                    ws.row_dimensions[cellule.row].height = max(hauteur, 18 * (texte.count("\n") + 3))
                cellule.value = texte
                if cellule.hyperlink is not None and "insee.fr" in texte:
                    cellule.hyperlink = texte
    titre = ws["A1"].value
    if isinstance(titre, str) and "MEL" not in titre:
        ws["A1"] = titre.replace("Base MAS", "Base MAS MEL", 1)


def adapter_textes_mel(workbook) -> None:
    """Présentation, Detail calcul et titres des onglets : vocabulaire communal au lieu de Roubaix / IRIS."""
    adapter_presentation_mel(workbook)
    if "Detail calcul" in workbook.sheetnames:
        for ligne in workbook["Detail calcul"].iter_rows():
            for cellule in ligne:
                if isinstance(cellule.value, str):
                    texte = cellule.value.replace("(total Roubaix)", "(total MEL)")
                    texte = texte.replace("Base MAS -", "Base MAS MEL -", 1) if "MEL" not in texte else texte
                    cellule.value = texte
    for ws in workbook.worksheets:
        if ws.title in {"Présentation", "Detail calcul"} or ws.title.startswith("Portrait"):
            continue
        titre = ws["A1"].value
        if isinstance(titre, str):
            titre = titre.replace("Données infra-communales", "Données communales MEL").replace("par IRIS", "par commune")
            ws["A1"] = titre
