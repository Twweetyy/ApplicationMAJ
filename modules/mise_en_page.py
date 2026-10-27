"""Mise en page des onglets de données : formats de nombres, largeurs, volets figés."""
import math
import re

from openpyxl.utils import get_column_letter

from .indicateurs import _precision_arrondi

FEUILLES_FIXES = {"Présentation", "Detail calcul"}
FORMATS = {0: "#,##0", 1: "#,##0.0", 2: "#,##0.00"}
LARGEUR_MIN, LARGEUR_MAX = 11, 32
LIGNES_ENTETE_MAX = 5
# Thèmes dont aucune colonne ne s'additionne (quartiles, médianes, taux Filosofi)
THEMES_NON_ADDITIFS = ("REV DEC", "REV DISP")


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


def _mettre_en_page_onglet(ws) -> None:
    entetes = [cellule.value for cellule in ws[2]]
    nombre_colonnes_geo = 8 if "Age : 0" in entetes else 7
    derniere_ligne = _derniere_ligne(ws)
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
        format_nombre = FORMATS.get(precision, "#,##0.00")

        longueur_valeurs = 0
        for ligne in range(3, derniere_ligne + 1):
            cellule = ws.cell(row=ligne, column=colonne)
            if isinstance(cellule.value, (int, float)) and not isinstance(cellule.value, bool):
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
