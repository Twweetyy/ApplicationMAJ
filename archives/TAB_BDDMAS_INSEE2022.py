"""
================================================================================
PROJET      : Traitement et structuration BDDMAS INSEE - Ville de Roubaix
FICHIER     : TAB_BDDMAS_INSEE2022.py
DATE        : 28/09/2026
PYTHON      : >= 3.11
DÉPENDANCES : pandas, openpyxl, tqdm, pyyaml (optionnel si chargeur custom)

DESCRIPTION :
  Automatisation de l'ingestion et structuration des bases thématiques INSEE (BDDMAS).
  Renommage dynamique des variables via les dictionnaires YAML locaux.
  Enrichissement géographique avec les données de Roubaix (Quartiers, NPNRU, etc.).
  Génération du classeur Excel officiel multi-onglets (Charte Mairie/MEL).
================================================================================
"""

import os
import pandas as pd
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.styles import Alignment, PatternFill, Font, Border, Side
from tqdm import tqdm

# ===========================================================================================
# 1. PARAMÈTRES ET CHEMINS
# ===========================================================================================
dossier_courant = os.path.dirname(os.path.abspath(__file__))
dossier_donnees = os.path.join(dossier_courant, "data")
dossier_dictionnaires = os.path.join(dossier_courant, "dictionnaires")

# Les fichiers sources bruts INSEE
fichier_pop = os.path.join(dossier_donnees, "base-ic-evol-struct-pop-2022.CSV")
fichier_log = os.path.join(dossier_donnees, "base-ic-logement-2022.CSV")
# (Tu pourras ajouter ACT_RES, COU_FAM, etc. ici de la même manière)

# Fichier de sortie Excel
fichier_excel_final = os.path.join(dossier_courant, "TAB_BDDMAS_INSEE2022_Tout_perimetre_Genere.xlsx")

# Dictionnaires
fichier_iris_roubaix = os.path.join(dossier_dictionnaires, "libelles_iris_roubaix.yml")
fichier_dico_pop = os.path.join(dossier_dictionnaires, "dictionnaire_variables_POP.yml")
fichier_dico_log = os.path.join(dossier_dictionnaires, "dictionnaire_variables_LOG.yml")

def charger_yml(chemin):
    """Lit un fichier clé: valeur YAML sans nécessiter de bibliothèque tierce."""
    mapping = {}
    if not os.path.exists(chemin):
        print(f"Attention : fichier introuvable -> {chemin}")
        return mapping
    with open(chemin, "r", encoding="utf-8") as f:
        for ligne in f:
            if ":" in ligne:
                cle, val = ligne.split(":", 1)
                cle = cle.strip().strip('"').strip("'")
                val = val.strip().strip('"').strip("'")
                mapping[cle] = val
    return mapping

# ===========================================================================================
# 2. CHARGEMENT DES DICTIONNAIRES & ENRICHISSEMENT
# ===========================================================================================
print("Chargement des dictionnaires géographiques...")
dict_iris = charger_yml(fichier_iris_roubaix)
dict_pop = charger_yml(fichier_dico_pop)
dict_log = charger_yml(fichier_dico_log)

def enrichir_donnees_spatiales(df):
    """
    Filtre le DataFrame sur Roubaix (59512) et ajoute les colonnes spatiales
    attendues par le classeur TAB_BDDMAS.
    """
    # 1. Filtrer uniquement les IRIS de Roubaix (commençant par 59512)
    df = df[df["IRIS"].astype(str).str.startswith("59512", na=False)].copy()
    
    # 2. Construction de l'enrichissement (Ordre spécifique du fichier attendu)
    # Dans un projet réel, ces valeurs proviennent d'autres dicts YAML (Secteurs, NPNRU...).
    # Ici, nous mettons les colonnes d'architecture en place, avec le Libellé IRIS réel.
    df.insert(0, "Libellé de l'Iris", df["IRIS"].map(dict_iris).fillna("NON LOCALISÉ"))
    df.insert(0, "Mairies de quartiers", "N/A")    # A remplacer avec ton dict secteurs_mairie.yml
    df.insert(0, "Grands quartiers", "N/A")        # A remplacer avec ton dict grand_quartier.yml
    df.insert(0, "Cités éducatives", "N/A")
    df.insert(0, "Contrats de Ville 2024 (CDV)", "N/A")
    df.insert(0, "Périmètres NPNRU", "N/A")
    df.insert(0, "Centres sociaux", "N/A")
    
    return df

def renommer_colonnes_insee(df, dictionnaire_variables):
    """
    Enlève le préfixe millésimé (ex: 'P22_', 'C22_') puis renomme via le YAML.
    """
    nouveaux_noms = {}
    for col in df.columns:
        # On supprime le préfixe Insee (ex: 'P22_POP' -> 'POP', 'C22_POP15P' -> 'POP15P')
        col_propre = col
        if col_propre.startswith(("P22_", "C22_", "P21_", "C21_")):
            col_propre = col_propre[4:]
            
        # On cherche la correspondance dans le YAML
        if col_propre in dictionnaire_variables:
            nouveaux_noms[col] = dictionnaire_variables[col_propre]
        else:
            nouveaux_noms[col] = col_propre # Par défaut, on garde la version sans préfixe
            
    df = df.rename(columns=nouveaux_noms)
    return df

# ===========================================================================================
# 3. PRÉPARATION DES DONNÉES THÉMATIQUES
# ===========================================================================================
print("Ingestion et nettoyage des fichiers sources INSEE...")

thematiques = []

# --- TRAITEMENT POPULATION ---
if os.path.exists(fichier_pop):
    df_pop = pd.read_csv(fichier_pop, sep=";", dtype=str)
    df_pop = enrichir_donnees_spatiales(df_pop)
    df_pop = renommer_colonnes_insee(df_pop, dict_pop)
    
    # Conversion en numérique pour permettre les totaux Excel
    cols_a_ignorer = ["Centres sociaux", "Périmètres NPNRU", "Contrats de Ville 2024 (CDV)", 
                      "Cités éducatives", "Grands quartiers", "Mairies de quartiers", 
                      "Libellé de l'Iris", "IRIS", "COM", "TYP_IRIS", "LAB_IRIS"]
    for col in df_pop.columns:
        if col not in cols_a_ignorer:
            df_pop[col] = pd.to_numeric(df_pop[col], errors='coerce')
            
    thematiques.append({"nom_onglet": "POP 2022", "titre": "Données infra-communales - Population", "data": df_pop})

# --- TRAITEMENT LOGEMENT ---
if os.path.exists(fichier_log):
    df_log = pd.read_csv(fichier_log, sep=";", dtype=str)
    df_log = enrichir_donnees_spatiales(df_log)
    df_log = renommer_colonnes_insee(df_log, dict_log)
    
    for col in df_log.columns:
        if col not in cols_a_ignorer:
            df_log[col] = pd.to_numeric(df_log[col], errors='coerce')
            
    thematiques.append({"nom_onglet": "LOG 2022", "titre": "Données infra-communales - Logement", "data": df_log})


# ===========================================================================================
# 4. FONCTIONS DE FORMATAGE EXCEL OPENPYXL
# ===========================================================================================
def ajuster_largeur_colonnes(worksheet, dataframe):
    for idx, col in enumerate(dataframe.columns):
        # Largeur max de 35 pour éviter des colonnes gigantesques
        max_len = min(max(len(str(col)), 12), 35)
        worksheet.column_dimensions[get_column_letter(idx + 1)].width = max_len

def formater_onglet_thematique(worksheet, dataframe, titre_thematique):
    """
    Applique la charte Roubaix :
    Ligne 1 : Titre + Formules SUBTOTAL dynamiques (Vert).
    Ligne 2 : Noms des colonnes (Bleu institutionnel).
    """
    # Ligne 2 : En-têtes (Bleu institutionnel)
    worksheet.row_dimensions[2].height = 65
    alignement_entete = Alignment(horizontal="center", vertical="center", wrap_text=True)
    fond_bleu = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    police_blanche = Font(color="FFFFFF", bold=True)
    
    for col_idx in range(1, worksheet.max_column + 1):
        cell = worksheet.cell(row=2, column=col_idx)
        cell.alignment = alignement_entete
        cell.font = police_blanche
        cell.fill = fond_bleu

    # Ligne 1 : Grand titre et Totaux (Vert dynamique)
    worksheet.row_dimensions[1].height = 40
    worksheet.cell(row=1, column=1, value=titre_thematique).font = Font(bold=True, size=14, color="1F497D")
    
    # On cherche où commencent les données numériques (après "Libellé de l'Iris")
    try:
        col_debut_valeurs = dataframe.columns.get_loc("Libellé de l'Iris") + 2
    except KeyError:
        col_debut_valeurs = 8 # Par défaut

    worksheet.cell(row=1, column=col_debut_valeurs - 1, value="Total").font = Font(bold=True, color="00B050")
    worksheet.cell(row=1, column=col_debut_valeurs - 1).alignment = Alignment(horizontal="right", vertical="center")

    for col_idx in range(col_debut_valeurs, worksheet.max_column + 1):
        lettre_col = get_column_letter(col_idx)
        # Formule SUBTOTAL(9, plage) pour s'actualiser avec les filtres
        formule = f"=SUBTOTAL(9,{lettre_col}3:{lettre_col}{worksheet.max_row})"
        cellule_total = worksheet.cell(row=1, column=col_idx, value=formule)
        cellule_total.font = Font(bold=True, color="00B050")
        cellule_total.fill = PatternFill(start_color="EBF1DE", end_color="EBF1DE", fill_type="solid")
        cellule_total.alignment = Alignment(horizontal="center", vertical="center")

    # Figer les volets (Sous les en-têtes et après le Libellé de l'Iris)
    lettre_figeage = get_column_letter(col_debut_valeurs)
    worksheet.freeze_panes = f"{lettre_figeage}3"

# ===========================================================================================
# 5. GÉNÉRATION DU FICHIER EXCEL FINAL
# ===========================================================================================
print("\n⏳ GÉNÉRATION DU FICHIER EXCEL FINAL (Veuillez patienter)...")

with pd.ExcelWriter(fichier_excel_final, engine="openpyxl") as writer:
    
    # --- 1. ONGLET PRÉSENTATION ---
    print(" -> Création de l'onglet : Présentation")
    worksheet_accueil = writer.book.create_sheet("Présentation", 0)
    worksheet_accueil.sheet_view.showGridLines = False 
    
    # Styles
    font_titre = Font(bold=True, size=16, color="FFFFFF")
    fill_titre = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    font_header = Font(bold=True, color="1F497D")
    fill_header = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
    font_onglet = Font(bold=True, color="1F497D")
    font_lien = Font(color="0000FF", underline="single")
    
    worksheet_accueil.column_dimensions['A'].width = 25
    worksheet_accueil.column_dimensions['B'].width = 15
    worksheet_accueil.column_dimensions['C'].width = 120
    worksheet_accueil.column_dimensions['D'].width = 60

    # Titre
    worksheet_accueil.merge_cells('A1:D1')
    cell_titre = worksheet_accueil['A1']
    cell_titre.value = "Base MAS - INSEE mise à jour 2022"
    cell_titre.font = font_titre
    cell_titre.fill = fill_titre
    cell_titre.alignment = Alignment(horizontal="center", vertical="center")
    worksheet_accueil.row_dimensions[1].height = 40

    # En-têtes Présentation
    headers = ["Onglet disponible", "Année", "Description", "Lien vers le dictionnaire de données"]
    for col_num, header_text in enumerate(headers, 1):
        cell = worksheet_accueil.cell(row=2, column=col_num, value=header_text)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center")
    worksheet_accueil.row_dimensions[2].height = 25

    # Données du tableau de bord
    donnees_presentation = [
        ["POP", 2022, "Indicateurs détaillés sur la POPULATION de Roubaix...", "https://www.insee.fr/fr/statistiques/8647014"],
        ["LOG", 2022, "Indicateurs détaillés sur des LOGEMENTS et parcs immobiliers...", "https://www.insee.fr/fr/statistiques/8647012"]
    ]

    fill_pair = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_impair = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    for i, row_data in enumerate(donnees_presentation):
        row_idx = i + 3
        fill_current = fill_pair if i % 2 == 1 else fill_impair
        worksheet_accueil.row_dimensions[row_idx].height = 35
        for col_idx, val in enumerate(row_data):
            cell = worksheet_accueil.cell(row=row_idx, column=col_idx+1, value=val)
            cell.fill = fill_current
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if col_idx == 0:
                cell.font = font_onglet
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 1:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 3:
                cell.font = font_lien
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.hyperlink = val

    # --- 2. ONGLETS THÉMATIQUES ---
    for theme in tqdm(thematiques, desc="Génération des onglets thématiques"):
        df_theme = theme["data"]
        
        # Exporter via pandas, en commençant à la ligne 1 (pour laisser la ligne 0 vide pour nos Totaux)
        df_theme.to_excel(writer, sheet_name=theme["nom_onglet"], index=False, startrow=1)
        worksheet_theme = writer.sheets[theme["nom_onglet"]]
        
        # Application du formatage
        ajuster_largeur_colonnes(worksheet_theme, df_theme)
        formater_onglet_thematique(worksheet_theme, df_theme, theme["titre"])
        
        # Ajout du Tableau natif Excel
        ref_tableau = f"A2:{get_column_letter(worksheet_theme.max_column)}{worksheet_theme.max_row}"
        nom_table = f"Table_{theme['nom_onglet'].replace(' ', '_')}"
        tab = Table(displayName=nom_table, ref=ref_tableau)
        tab.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=True)
        worksheet_theme.add_table(tab)

print(f"\n✅ Terminé avec succès : {fichier_excel_final}")