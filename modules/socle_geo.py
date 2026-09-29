import os
import pandas as pd
import yaml

def charger_referentiel_mas(chemin_fichier: str) -> pd.DataFrame:
    """
    Charge le fichier Périmètres_MAS.csv et renomme les colonnes
    pour correspondre aux en-têtes attendus dans le fichier Excel final.
    """
    if not os.path.exists(chemin_fichier):
        print(f"Erreur : Le fichier de périmètre est introuvable -> {chemin_fichier}")
        return pd.DataFrame()

    df_perimetre = pd.read_csv(chemin_fichier, dtype={"IRIS": str})
    
    # Renommage strict selon la charte du projet (comme dans utils.py)
    df_perimetre = df_perimetre.rename(columns={
        "Libellé_IRIS": "Libellé de l'Iris",
        "Quartier": "Mairies de quartiers",
        "Centre_Social": "Centres sociaux",
        "Périmètre_NPNRU": "Périmètres NPNRU",
        "ContratVille2024": "Contrats de Ville 2024 (CDV)",
        "Cité_Educative": "Cités éducatives",
        "Grands_quartiers": "Grands quartiers",
    })
    
    # Sécurité : forcer l'IRIS en texte (str) pour éviter la perte du zéro initial
    df_perimetre["IRIS"] = df_perimetre["IRIS"].astype(str).str.zfill(9)
    
    return df_perimetre

def joindre_perimetre(dico_fichiers: dict, df_perimetre: pd.DataFrame) -> dict:
    """
    Joint le périmètre géographique à tous les DataFrames thématiques.
    Place les colonnes de zonage en tête du tableau (Colonnes A à G).
    """
    dico_joint = {}
    
    colonnes_ordre = [
        "Centres sociaux", 
        "Périmètres NPNRU", 
        "Contrats de Ville 2024 (CDV)", 
        "Cités éducatives", 
        "Grands quartiers", 
        "Mairies de quartiers", 
        "Libellé de l'Iris",
        "IRIS"
    ]

    for nom_fichier, df in dico_fichiers.items():
        if df is None or df.empty:
            continue
            
        # Jointure (Left Join pour garder tous les IRIS Insee du DataFrame)
        df_merged = df.merge(df_perimetre, on="IRIS", how="left")
        
        # Réorganisation des colonnes : on met le zonage au début, puis le reste
        colonnes_restantes = [col for col in df_merged.columns if col not in colonnes_ordre]
        nouvel_ordre = colonnes_ordre + colonnes_restantes
        
        # Filtrer pour ne garder que les colonnes qui existent vraiment
        nouvel_ordre = [col for col in nouvel_ordre if col in df_merged.columns]
        
        dico_joint[nom_fichier] = df_merged[nouvel_ordre]

    return dico_joint


def ajouter_superficies_iris(dico_fichiers: dict, chemin_fichier: str) -> dict:
    """Ajoute la superficie en km2 à chaque table depuis le dictionnaire IRIS."""
    if not os.path.exists(chemin_fichier):
        print(f"Attention : dictionnaire des superficies introuvable -> {chemin_fichier}")
        return dico_fichiers

    with open(chemin_fichier, "r", encoding="utf-8") as fichier:
        superficies = yaml.safe_load(fichier) or {}
    superficies = {str(code): valeur for code, valeur in superficies.items()}

    for nom, dataframe in dico_fichiers.items():
        if "IRIS" in dataframe.columns:
            dataframe["Superficie en km²"] = pd.to_numeric(
                dataframe["IRIS"].astype(str).map(superficies),
                errors="coerce",
            )
            dico_fichiers[nom] = dataframe
    return dico_fichiers