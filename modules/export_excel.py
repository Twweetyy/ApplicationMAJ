import os
from copy import copy
import pandas as pd
import openpyxl
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
import yaml
from tqdm.auto import tqdm

def charger_titres_onglets(chemin_yaml: str) -> dict:
    """Charge le dictionnaire contenant les grands titres de chaque onglet."""
    if not os.path.exists(chemin_yaml):
        return {}
    with open(chemin_yaml, "r", encoding="UTF-8") as file:
        return yaml.safe_load(file) or {}

def formater_onglet_thematique(worksheet, dataframe, titre_onglet):
    """
    Applique la charte graphique Mairie/MEL sur un onglet de données :
    - Ligne 1 : Titre principal (A1) et Sous-totaux dynamiques (Vert).
    - Ligne 2 : En-têtes (Gris pour Géo, Bleu pour Insee, Orange pour Calculs).
    """
    # --- DÉFINITION DES STYLES ---
    font_bold = Font(bold=True)
    font_total = Font(bold=True, color="00B050")
    font_titre = Font(bold=True, color="800000", size=12)
    
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center")
    
    fill_geo = PatternFill(start_color="BFBFBF", end_color="BFBFBF", fill_type="solid")
    fill_data_bleu = PatternFill(start_color="91DEFF", end_color="91DEFF", fill_type="solid")
    fill_data_orange = PatternFill(start_color="F8CBAD", end_color="F8CBAD", fill_type="solid")
    fill_total_vert = PatternFill(start_color="EBF1DE", end_color="EBF1DE", fill_type="solid")
    fill_gris_clair = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

    border_gris = Border(
        left=Side(style="thin", color="BFBFBF"), right=Side(style="thin", color="BFBFBF"),
        top=Side(style="thin", color="BFBFBF"), bottom=Side(style="thin", color="BFBFBF")
    )

    # Paramétrage des dimensions
    worksheet.row_dimensions[1].height = 30
    worksheet.row_dimensions[2].height = 80

    # Détection des séparations de colonnes (Géo vs Données vs Calculs)
    col_geo_max = 8 # Par défaut, les colonnes A à H sont géographiques
    
    # On cherche "Superficie en km²" ou la fin des données brutes pour appliquer l'orange
    try:
        col_calc_start = dataframe.columns.get_loc("Superficie en km²") + 1
    except KeyError:
        col_calc_start = worksheet.max_column - 5 # Approximation si la colonne n'existe pas

    # --- ÉCRITURE DE LA LIGNE 1 (Titre et Sous-Totaux) ---
    worksheet.cell(row=1, column=1, value=titre_onglet).font = font_titre
    worksheet.cell(row=1, column=1).alignment = align_left
    
    worksheet.cell(row=1, column=col_geo_max, value="Total").font = font_bold
    worksheet.cell(row=1, column=col_geo_max).alignment = align_center

    for col_idx in range(col_geo_max + 1, worksheet.max_column + 1):
        lettre_col = get_column_letter(col_idx)
        # Formule dynamique prenant en compte les filtres utilisateurs
        formule = f"=SUBTOTAL(9,{lettre_col}3:{lettre_col}{worksheet.max_row})"
        
        cell_total = worksheet.cell(row=1, column=col_idx, value=formule)
        cell_total.font = font_total
        cell_total.fill = fill_total_vert
        cell_total.alignment = align_center
        cell_total.border = border_gris

    # --- APPLICATION DES STYLES POUR LE RESTE DU TABLEAU ---
    for row_idx in range(2, worksheet.max_row + 1):
        for col_idx in range(1, worksheet.max_column + 1):
            cell = worksheet.cell(row=row_idx, column=col_idx)
            cell.border = border_gris
            
            # Ligne 2 (En-têtes)
            if row_idx == 2:
                cell.alignment = align_center
                cell.font = font_bold
                
                # Ajustement largeur (spécifique pour le libellé IRIS)
                largeur = 24 if cell.value == "Libellé de l'Iris" else 15
                worksheet.column_dimensions[get_column_letter(col_idx)].width = largeur
                
                # Couleurs des en-têtes
                if col_idx <= col_geo_max:
                    cell.fill = fill_geo
                elif col_idx < col_calc_start:
                    cell.fill = fill_data_bleu
                else:
                    cell.fill = fill_data_orange
            
            # Lignes de données (3 et +)
            else:
                if col_idx <= col_geo_max:
                    cell.font = font_bold
                    cell.fill = fill_gris_clair
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="right", vertical="center")

    # Figeage des volets (sous les en-têtes, après le zonage géo)
    lettre_fige = get_column_letter(col_geo_max + 1)
    worksheet.freeze_panes = f"{lettre_fige}3"

def preparer_dataframe_modele(nom_onglet: str, dataframe: pd.DataFrame) -> pd.DataFrame:
    """Adapte les colonnes calculées aux libellés du modèle Excel BDDMAS."""
    resultat = dataframe.copy()
    if nom_onglet.startswith("PETITE ENFANCE"):
        resultat = resultat.rename(columns={
            "Contrats de Ville 2024 (CDV)": "Contrats de Ville (CDV)",
            "Grands quartiers": "Quartiers SIG (Grands quartiers)",
            "Mairies de quartiers": "Mairies de qartiers",
        })
        colonnes_ages = [f"Age : {age}" for age in range(18) if f"Age : {age}" in resultat.columns]
        resultat["TOTAL 0-17"] = resultat[colonnes_ages].sum(axis=1)
        resultat["Crèches"] = ""
    if "IRIS" in resultat.columns:
        resultat = resultat.drop(columns="IRIS")
    return resultat


def _generer_depuis_modele(
    dico_fichiers: dict,
    chemin_sortie: str,
    chemin_infos_onglets: str,
    chemin_modele: str,
) -> None:
    """Remplit une copie du classeur modèle sans conserver ses lignes d'exemple."""
    titres = charger_titres_onglets(chemin_infos_onglets)
    workbook = load_workbook(chemin_modele)
    feuilles_fixes = {"Présentation", "Detail calcul"}

    for worksheet in workbook.worksheets:
        if worksheet.title in feuilles_fixes:
            continue
        for row in worksheet.iter_rows(min_row=3, max_row=worksheet.max_row):
            for cell in row:
                cell.value = None

    for nom_onglet, dataframe in dico_fichiers.items():
        if nom_onglet not in workbook.sheetnames:
            if nom_onglet == "PETITE ENFANCE MILLÉSIME" and "PETITE ENFANCE 2022" in workbook.sheetnames:
                worksheet = workbook.copy_worksheet(workbook["PETITE ENFANCE 2022"])
                worksheet.title = nom_onglet
            else:
                worksheet = workbook.create_sheet(nom_onglet[:31])
                worksheet.cell(row=2, column=1, value="IRIS")
        else:
            worksheet = workbook[nom_onglet]

        donnees = preparer_dataframe_modele(nom_onglet, dataframe)
        entetes_modele = [
            worksheet.cell(row=2, column=colonne).value
            for colonne in range(1, worksheet.max_column + 1)
        ]
        derniere_ligne = len(donnees) + 2

        if derniere_ligne > worksheet.max_row and worksheet.max_row >= 3:
            for ligne in range(worksheet.max_row + 1, derniere_ligne + 1):
                for colonne in range(1, worksheet.max_column + 1):
                    cellule = worksheet.cell(row=ligne, column=colonne)
                    modele_cellule = worksheet.cell(row=3, column=colonne)
                    if modele_cellule.has_style:
                        cellule._style = copy(modele_cellule._style)
                    if modele_cellule.number_format:
                        cellule.number_format = modele_cellule.number_format

        lignes = tqdm(
            donnees.iterrows(),
            total=len(donnees),
            desc=f"Écriture Excel : {nom_onglet}",
            unit="lignes",
            leave=False,
            dynamic_ncols=True,
        )
        for ligne, (_, enregistrement) in enumerate(lignes, start=3):
            for colonne, entete in enumerate(entetes_modele, start=1):
                if entete not in donnees.columns:
                    continue
                valeur = enregistrement[entete]
                if pd.isna(valeur):
                    valeur = None
                elif hasattr(valeur, "item"):
                    valeur = valeur.item()
                worksheet.cell(row=ligne, column=colonne, value=valeur)

        titre = titres.get(nom_onglet, f"Données infra-communales - {nom_onglet}")
        worksheet.cell(row=1, column=1, value=titre)
        nombre_colonnes_geo = 8 if "Age : 0" in entetes_modele else 7
        worksheet.cell(row=1, column=nombre_colonnes_geo, value="Total")
        derniere_ligne_donnees = max(derniere_ligne, 3)
        for colonne in range(nombre_colonnes_geo + 1, worksheet.max_column + 1):
            lettre = get_column_letter(colonne)
            worksheet.cell(
                row=1,
                column=colonne,
                value=f"=SUBTOTAL(9,{lettre}3:{lettre}{derniere_ligne_donnees})",
            )

    os.makedirs(os.path.dirname(os.path.abspath(chemin_sortie)), exist_ok=True)
    workbook.save(chemin_sortie)


def generer_fichier_bddmas(
    dico_fichiers: dict,
    chemin_sortie: str,
    chemin_infos_onglets: str,
    chemin_modele: str = None,
):
    """
    Génère le classeur Excel final à partir du dictionnaire de DataFrames.
    """
    if chemin_modele and os.path.exists(chemin_modele):
        print("GÉNÉRATION DU CLASSEUR À PARTIR DU MODÈLE...")
        _generer_depuis_modele(dico_fichiers, chemin_sortie, chemin_infos_onglets, chemin_modele)
        print(f"Fichier Excel enregistré avec succès sous : {chemin_sortie}")
        return

    print("\nGÉNÉRATION DU FICHIER EXCEL FINAL...")
    titres_onglets = charger_titres_onglets(chemin_infos_onglets)
    
    with pd.ExcelWriter(chemin_sortie, engine='openpyxl') as writer:
        
        # --- 1. Création de l'onglet de Présentation ---
        ws_accueil = writer.book.create_sheet("Présentation", 0)
        ws_accueil.sheet_view.showGridLines = False 
        
        ws_accueil.merge_cells('A1:C1')
        ws_accueil['A1'].value = "Base MAS - INSEE mise à jour 2022"
        ws_accueil['A1'].font = Font(bold=True, size=16, color="FFFFFF")
        ws_accueil['A1'].fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        ws_accueil['A1'].alignment = Alignment(horizontal="center", vertical="center")
        ws_accueil.row_dimensions[1].height = 40
        
        # --- 2. Boucle sur les onglets thématiques ---
        for nom_onglet, df in dico_fichiers.items():
            print(f" -> Export et formatage de l'onglet : {nom_onglet}")
            
            # Export du DataFrame avec startrow=1 (laisse la ligne 1 vierge pour nos Totaux)
            df.to_excel(writer, sheet_name=nom_onglet, index=False, startrow=1)
            
            # Récupération de la feuille pour le formatage
            worksheet = writer.sheets[nom_onglet]
            titre_principal = titres_onglets.get(nom_onglet, f"Données infra-communales - {nom_onglet}")
            
            formater_onglet_thematique(worksheet, df, titre_principal)
            
    print(f"Fichier Excel enregistré avec succès sous : {chemin_sortie}")