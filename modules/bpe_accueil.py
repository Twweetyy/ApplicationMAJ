"""Onglet « Accueil » du classeur BPE : chiffres clés des équipements, par domaine.

Les comptages sont des formules Excel (NB.SI) sur l'onglet BPE_brut : ils suivent le classeur.
Seuls le nombre de types d'équipement et de communes sont écrits en valeur (comptage de valeurs
distinctes, trop lourd en formule sur la MEL).
"""
import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

NOM_ONGLET = "Accueil"
NB_TYPES_PAR_DOMAINE = 6
BLOCS_PAR_LIGNE = 4
BLEU, GRIS, BLANC = "1F4E78", "595959", "FFFFFF"

# Couleur foncée, couleur claire par domaine BPE
COULEURS_DOMAINES = {
    "A": ("2E75B6", "DEEAF6"),
    "B": ("C55A11", "FBE5D6"),
    "C": ("7030A0", "EADCF4"),
    "D": ("C00000", "F8DEDE"),
    "E": ("548235", "E2F0D9"),
    "F": ("BF8F00", "FFF2CC"),
    "G": ("008080", "DDF1F1"),
}
COULEUR_DEFAUT = ("595959", "EDEDED")
LIBELLES_COURTS = {
    "A": "services aux particuliers",
    "B": "commerces",
    "C": "enseignement",
    "D": "santé et action sociale",
    "E": "transports et déplacements",
    "F": "sports, loisirs et culture",
    "G": "tourisme",
}


def _enumeration(elements: list[str]) -> str:
    return elements[0] if len(elements) == 1 else ", ".join(elements[:-1]) + " et " + elements[-1]


def _plage(df: pd.DataFrame, colonne: str, onglet: str) -> str:
    lettre = get_column_letter(list(df.columns).index(colonne) + 1)
    return f"'{onglet}'!${lettre}$2:${lettre}${len(df) + 1}"


def _fusion(ws, plage, valeur=None, font=None, fill=None, align=None):
    ws.merge_cells(plage)
    cellule = ws[plage.split(":")[0]]
    cellule.value = valeur
    if fill:
        for ligne in ws[plage]:
            for c in ligne:
                c.fill = fill
    if font:
        cellule.font = font
    cellule.alignment = align or Alignment(vertical="center", wrap_text=True)
    return cellule


def _description(df: pd.DataFrame, annee: str, perimetre: str, domaines: list[str]) -> str:
    territoire = "la MEL" if perimetre == "mel" else "Roubaix"
    contenus = _enumeration([LIBELLES_COURTS.get(code, code) for code in domaines]) if domaines else "équipements"
    rattachement = (
        "rattachés à leur commune (95 communes de la Métropole Européenne de Lille)"
        if perimetre == "mel"
        else "rattachés à leur IRIS, secteur de mairie, quartier historique et grand quartier"
    )
    return (
        f"Ce classeur rassemble la Base permanente des équipements (BPE {annee}) de l'Insee pour {territoire} : "
        f"{len(df):,} équipements".replace(",", " ")
        + f" ({contenus}), géolocalisés à l'adresse et {rattachement}.\n"
        "Cette page en résume les chiffres clés, par domaine, avec les types d'équipement les plus nombreux. "
        "Les valeurs sont calculées à partir de l'onglet BPE_brut ; le lien sous chaque domaine ouvre son onglet. "
        "Description des onglets, liens Insee et précisions : onglet « Sources »."
    )


def ecrire_accueil_chiffres_cles(
    ws,
    df_bpe: pd.DataFrame,
    annee: str,
    perimetre: str,
    onglets_domaines: list[tuple[str, str]],
    dictionnaire: dict,
    onglet_brut: str,
) -> None:
    mel = perimetre == "mel"
    ws.sheet_view.showGridLines = False
    for i, largeur in enumerate([2] + [34, 11, 3] * BLOCS_PAR_LIGNE, start=1):
        ws.column_dimensions[get_column_letter(i)].width = largeur
    fin = get_column_letter(1 + 3 * BLOCS_PAR_LIGNE - 1)

    territoire = "la MEL" if mel else "Roubaix"
    _fusion(ws, f"B2:{fin}2", f"Équipements de {territoire} · BPE {annee}", Font(bold=True, size=20, color=BLEU))
    ws.row_dimensions[2].height = 34
    domaines = [code for code, _ in onglets_domaines]
    _fusion(ws, f"B3:{fin}3", _description(df_bpe, annee, perimetre, domaines), Font(size=11, color=GRIS),
            align=Alignment(wrap_text=True, vertical="top"))
    ws.row_dimensions[3].height = 66

    plage_id = _plage(df_bpe, "OBJECTID", onglet_brut)
    plage_domaine = _plage(df_bpe, "Code Domaine d'appartenance", onglet_brut)
    plage_type = _plage(df_bpe, "Code Type d'équipement", onglet_brut)
    plage_gps = _plage(df_bpe, "Latitude et longitude GPS", onglet_brut)
    total = f"COUNT({plage_id})"

    # Bandeau de 4 chiffres clés
    tuiles = [
        ("Équipements recensés", f"={total}", "#,##0"),
        ("Types d'équipement présents", int(df_bpe["Code Type d'équipement"].replace("", pd.NA).nunique()), "#,##0"),
        ("Équipements géolocalisés", f'=IFERROR(COUNTIF({plage_gps},"?*")/{total},"")', "0.0 %"),
    ]
    if mel:
        tuiles.append(("Communes avec au moins un équipement", int(df_bpe["Code Insee"].replace("", pd.NA).nunique()), "#,##0"))
    else:
        plage_iris = _plage(df_bpe, "Code IRIS", onglet_brut)
        tuiles.append(("Équipements localisés à l'IRIS", f'=IFERROR(1-COUNTIF({plage_iris},"*_IND")/{total},"")', "0.0 %"))
    fond_tuile = PatternFill("solid", fgColor="F2F2F2")
    for k, (libelle, valeur, fmt) in enumerate(tuiles):
        c1, c2 = get_column_letter(2 + 3 * k), get_column_letter(3 + 3 * k)
        _fusion(ws, f"{c1}5:{c2}5", libelle, Font(size=10, color=GRIS), fond_tuile,
                Alignment(horizontal="center", vertical="center"))
        cellule = _fusion(ws, f"{c1}6:{c2}6", valeur, Font(bold=True, size=22, color=BLEU), fond_tuile,
                          Alignment(horizontal="center", vertical="center"))
        cellule.number_format = fmt
    ws.row_dimensions[5].height = 22
    ws.row_dimensions[6].height = 38

    # Un bloc par domaine : effectif, part, types les plus nombreux
    filet = Border(top=Side(style="hair", color="BFBFBF"))
    libelles_types = dictionnaire.get("TYPEQU", {})
    hauteur_bloc = 4 + NB_TYPES_PAR_DOMAINE + 1
    for index, (code, nom_onglet) in enumerate(onglets_domaines):
        fonce, clair = COULEURS_DOMAINES.get(code, COULEUR_DEFAUT)
        k = index % BLOCS_PAR_LIGNE
        haut = 8 + (index // BLOCS_PAR_LIGNE) * (hauteur_bloc + 1)
        c1, c2 = get_column_letter(2 + 3 * k), get_column_letter(3 + 3 * k)
        libelle_domaine = dictionnaire.get("DOM", {}).get(code) or nom_onglet.split(" - ", 1)[-1]
        _fusion(ws, f"{c1}{haut}:{c2}{haut}", str(libelle_domaine).upper(),
                Font(bold=True, size=12, color=BLANC), PatternFill("solid", fgColor=fonce),
                Alignment(horizontal="center", vertical="center", wrap_text=True))
        ws.row_dimensions[haut].height = 30

        nb_domaine = f'COUNTIF({plage_domaine},"{code}")'
        for decalage, (libelle, formule, fmt, taille) in enumerate([
            ("Équipements", f"={nb_domaine}", "#,##0", 14),
            ("Part de l'ensemble des équipements", f'=IFERROR({nb_domaine}/{total},"")', "0.0 %", 12),
        ], start=1):
            a, b = ws[f"{c1}{haut + decalage}"], ws[f"{c2}{haut + decalage}"]
            a.value, a.font = libelle, Font(size=10, bold=decalage == 1)
            a.fill = b.fill = PatternFill("solid", fgColor=clair)
            a.alignment = Alignment(vertical="center", wrap_text=True)
            b.value, b.number_format = formule, fmt
            b.font = Font(bold=True, size=taille, color=fonce)
            b.alignment = Alignment(horizontal="right", vertical="center")
            ws.row_dimensions[haut + decalage].height = 24

        sous_titre = ws[f"{c1}{haut + 3}"]
        sous_titre.value = "Types d'équipement les plus nombreux"
        sous_titre.font = Font(size=8, italic=True, color=GRIS)
        types = (
            df_bpe.loc[df_bpe["Code Domaine d'appartenance"] == code, "Code Type d'équipement"]
            .replace("", pd.NA).dropna().value_counts().head(NB_TYPES_PAR_DOMAINE)
        )
        for rang, code_type in enumerate(types.index, start=1):
            ligne = haut + 3 + rang
            a, b = ws[f"{c1}{ligne}"], ws[f"{c2}{ligne}"]
            a.value = str(libelles_types.get(code_type, code_type)).capitalize()
            a.font = Font(size=9)
            a.alignment = Alignment(wrap_text=True, vertical="center")
            b.value = f'=COUNTIF({plage_type},"{code_type}")'
            b.number_format = "#,##0"
            b.font = Font(bold=True, size=10, color=fonce)
            b.alignment = Alignment(horizontal="right", vertical="center")
            a.border = b.border = filet
            ws.row_dimensions[ligne].height = 26
        lien = ws[f"{c1}{haut + hauteur_bloc - 1}"]
        lien.value = f"Voir l'onglet {nom_onglet}"
        lien.hyperlink = f"#'{nom_onglet}'!A1"
        lien.font = Font(size=8, color=GRIS, underline="single")

    lignes_blocs = -(-len(onglets_domaines) // BLOCS_PAR_LIGNE)
    r = 8 + lignes_blocs * (hauteur_bloc + 1) + 1
    _fusion(ws, f"B{r}:{fin}{r}", "À savoir", Font(bold=True, color=BLANC), PatternFill("solid", fgColor=GRIS))
    notes = [
        f"Source : Insee, Base permanente des équipements {annee}. Un équipement = un lieu de service (une pharmacie, "
        "une école, un terrain de sport…), pas un établissement employeur.",
        f"Les valeurs sont des formules sur l'onglet {onglet_brut} : elles suivent le classeur. "
        "Le nombre de types d'équipement" + (" et de communes" if mel else "") + " est écrit en valeur.",
        "Le géocodage dépend de la qualité des adresses : une marge d'erreur de positionnement est possible.",
    ]
    for i, note in enumerate(notes, start=1):
        _fusion(ws, f"B{r + i}:{fin}{r + i}", "• " + note, Font(size=9))
        ws.row_dimensions[r + i].height = 18
    ws.sheet_view.topLeftCell = "A1"
