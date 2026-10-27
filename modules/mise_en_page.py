"""Mise en page des onglets de données : formats de nombres, largeurs, volets figés."""
import math
import re

from openpyxl.utils import get_column_letter, range_boundaries

from .indicateurs import _precision_arrondi

FEUILLES_FIXES = {"Présentation", "Detail calcul"}
FORMATS = {0: "#,##0", 1: "#,##0.0", 2: "#,##0.00"}
LARGEUR_MIN, LARGEUR_MAX = 11, 32
LIGNES_ENTETE_MAX = 5
# Thèmes dont aucune colonne ne s'additionne (quartiles, médianes, taux Filosofi)
THEMES_NON_ADDITIFS = ("REV DEC", "REV DISP")
# Colonnes du modèle sans source de données : supprimées si vides
COLONNES_SANS_SOURCE = {"Crèches"}


def _est_additive(nom_colonne: str, nom_feuille: str, precision: int) -> bool:
    """Une somme sur Roubaix n'a de sens que pour des effectifs (et la superficie)."""
    if nom_feuille.startswith(THEMES_NON_ADDITIFS):
        return False
    nom = nom_colonne.strip().casefold()
    if nom.startswith("superficie"):
        return True
    if precision >= 1:
        return False
    return not re.search(r"moyen|médian|median|quartile|décile|decile|loyer|€", nom)


def _derniere_ligne(ws) -> int:
    ligne = ws.max_row
    while ligne > 3 and all(cellule.value in (None, "") for cellule in ws[ligne]):
        ligne -= 1
    return ligne


def _supprimer_colonnes_vides(ws, noms=COLONNES_SANS_SOURCE) -> None:
    """Retire les colonnes du modèle sans source (ex. « Crèches ») quand elles sont vides."""
    derniere_ligne = _derniere_ligne(ws)
    for colonne in range(ws.max_column, 0, -1):
        if ws.cell(row=2, column=colonne).value not in noms:
            continue
        if any(ws.cell(row=ligne, column=colonne).value not in (None, "") for ligne in range(3, derniere_ligne + 1)):
            continue
        # Largeurs : openpyxl ne les décale pas avec delete_cols
        largeurs = {
            c: ws.column_dimensions[get_column_letter(c)].width
            for c in range(colonne + 1, ws.max_column + 1)
        }
        ws.delete_cols(colonne)
        for c, largeur in largeurs.items():
            if largeur:
                ws.column_dimensions[get_column_letter(c - 1)].width = largeur
        # Tableau Excel : plage et colonnes
        for tableau in ws.tables.values():
            min_col, min_row, max_col, max_row = range_boundaries(tableau.ref)
            if not min_col <= colonne <= max_col:
                continue
            tableau.ref = f"{get_column_letter(min_col)}{min_row}:{get_column_letter(max_col - 1)}{max_row}"
            del tableau.tableColumns[colonne - min_col]
            for i, colonne_tableau in enumerate(tableau.tableColumns, start=1):
                colonne_tableau.id = i
            if tableau.autoFilter is not None:
                tableau.autoFilter.ref = tableau.ref
        # Ligne Total : les SUBTOTAL gardent l'ancienne lettre, on les réécrit
        for c in range(colonne, ws.max_column + 1):
            cellule = ws.cell(row=1, column=c)
            if isinstance(cellule.value, str) and cellule.value.startswith("=SUBTOTAL"):
                lettre = get_column_letter(c)
                cellule.value = f"=SUBTOTAL(9,{lettre}3:{lettre}{derniere_ligne})"


def _mettre_en_page_onglet(ws) -> None:
    _supprimer_colonnes_vides(ws)
    entetes = [cellule.value for cellule in ws[2]]
    # Colonnes géo = jusqu'au libellé IRIS inclus (7, ou 8 si « Crèches » est restée)
    nombre_colonnes_geo = entetes.index("Libellé de l'Iris") + 1 if "Libellé de l'Iris" in entetes else 7
    derniere_ligne = _derniere_ligne(ws)
    # Le modèle petite enfance s'ouvre en F1 : sans ça, A-E restent cachées derrière le volet
    ws.sheet_view.topLeftCell = "A1"
    ws.freeze_panes = ws.cell(row=3, column=nombre_colonnes_geo + 1)

    lignes_entete = 2
    for colonne in range(nombre_colonnes_geo + 1, len(entetes) + 1):
        entete = entetes[colonne - 1]
        if entete in (None, ""):
            continue
        entete = str(entete)
        precision = _precision_arrondi(entete, ws.title)
        if precision is None:
            continue
        cellules = [
            ws.cell(row=ligne, column=colonne)
            for ligne in range(3, derniere_ligne + 1)
            if isinstance(ws.cell(row=ligne, column=colonne).value, (int, float))
            and not isinstance(ws.cell(row=ligne, column=colonne).value, bool)
        ]
        # Pas plus de décimales affichées que la source n'en contient (RPLS : 9,3 et non 9,30)
        decimales_source = max(
            (len(f"{cellule.value:.{precision}f}".rstrip("0").split(".")[1]) if precision else 0 for cellule in cellules),
            default=precision,
        )
        precision = min(precision, max(decimales_source, 1 if precision else 0))
        format_nombre = FORMATS.get(precision, "#,##0.00")

        longueur_valeurs = 0
        for cellule in cellules:
            cellule.number_format = format_nombre
            longueur_valeurs = max(longueur_valeurs, len(f"{cellule.value:,.{precision}f}"))

        total = ws.cell(row=1, column=colonne)
        if isinstance(total.value, str) and total.value.startswith("=SUBTOTAL"):
            if _est_additive(entete, ws.title, precision):
                total.number_format = format_nombre
            else:
                total.value = None

        # Largeur : l'en-tête doit tenir sur 5 lignes, les nombres sur une seule
        plus_long_mot = max((len(mot) for mot in entete.split()), default=0)
        largeur = max(math.ceil(len(entete) / LIGNES_ENTETE_MAX) + 2, plus_long_mot + 2, longueur_valeurs + 3)
        largeur = min(max(largeur, LARGEUR_MIN), LARGEUR_MAX)
        ws.column_dimensions[get_column_letter(colonne)].width = largeur
        lignes_entete = max(lignes_entete, math.ceil(len(entete) * 1.1 / largeur))

    ws.row_dimensions[2].height = min(lignes_entete, LIGNES_ENTETE_MAX + 1) * 15 + 5


def appliquer_mise_en_page(workbook) -> None:
    """Formats de nombres, largeurs de colonnes et volets figés sur chaque onglet de données."""
    for ws in workbook.worksheets:
        if ws.title in FEUILLES_FIXES or ws.max_row < 3:
            continue
        _mettre_en_page_onglet(ws)
