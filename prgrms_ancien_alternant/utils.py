import os
import re
import yaml
import pandas as pd
import openpyxl as pyxl
from openpyxl.utils import get_column_letter
from openpyxl import load_workbook


"""
Fonction permettant de joindre à un dataframe la liste des libellés des IRIS
Paramètres :
- df : dataframe sur lequel joindre
- libelles : dictionnaire contenant les libellés des IRIS
Retourne :
- new_df : dataframe avec les libellés des IRIS
"""
def join_iris_libelles(df: pd.DataFrame, libelles: dict) -> pd.DataFrame:
    new_df = df.copy()
    new_df.columns = [ele.upper() for ele in new_df.columns]
    # Si le tableau a une colonne se nommant "IRIS", il l'utilise pour joindre les libelles
    if "IRIS" in [ele.upper() for ele in df.columns]:
        new_df["LIBIRIS"] = new_df["IRIS"].astype(str).map(libelles)
    # Sinon, utilise la colonne "CODGEO"
    elif "CODGEO" in [ele.upper() for ele in df.columns]:
        new_df["LIBIRIS"] = new_df["CODGEO"].astype(str).map(libelles)
    return new_df   


"""
Fonction permettant de joindre à un dataframe la liste des superficies associées aux IRIS
Paramètres :
- df : dataframe sur lequel joindre
- superficies : dictionnaire contenant les superficies des IRIS
Retourne :
- new_df : dataframe avec les superficies des IRIS
"""
def join_iris_superficies(df: pd.DataFrame, superficies: dict) -> pd.DataFrame:
    new_df = df.copy()
    # Si le tableau a une colonne se nommant "IRIS", il l'utilise pour joindre les libelles
    if "IRIS" in [ele.upper() for ele in df.columns]:
        new_df["Superficie en km²"] = new_df["IRIS"].astype(str).map(superficies)
    # Sinon, utilise la colonne "CODGEO"
    elif "CODGEO" in [ele.upper() for ele in df.columns]:
        new_df["Superficie en km²"] = new_df["CODGEO"].astype(str).map(superficies)
    return new_df


def join_iris_perimetre_mas(df_dict: dict, df_perimetre: pd.DataFrame) -> dict:
    # Vérifier si df_perimetre est un DataFrame
    if not isinstance(df_perimetre, pd.DataFrame):
        raise ValueError(f"df_perimetre doit être un DataFrame, mais c'est un objet de type {type(df_perimetre)}.")

    # Créer un dictionnaire pour stocker les résultats de la jointure
    joined_dict = {}

    # Liste de l'ordre des colonnes à insérer en début de DataFrame
    ordered_columns = [
        "Centres sociaux", 
        "Périmètres NPNRU", 
        "Contrats de Ville 2024 (CDV)", 
        "Cités éducatives", 
        "Grands quartiers", 
        "Mairies de quartiers", 
        "Libellé de l'Iris"
    ]

    # Vérifier que le dictionnaire 'df_dict' contient des DataFrames
    for key, df in df_dict.items():
        # Faire une copie de chaque DataFrame pour éviter la modification des données d'origine
        new_df = df.copy()

        # Conversion des colonnes 'IRIS' ou 'Code géographique' en chaîne de caractères
        if "IRIS" in new_df.columns:
            new_df["IRIS"] = new_df["IRIS"].astype(str)
        if "Code géographique" in new_df.columns:
            new_df["Code géographique"] = new_df["Code géographique"].astype(str)

        # Conversion des colonnes 'IRIS' dans df_perimetre en chaîne de caractères
        if "IRIS" in df_perimetre.columns:
            df_perimetre["IRIS"] = df_perimetre["IRIS"].astype(str)
        if "Code géographique" in df_perimetre.columns:
            df_perimetre["Code géographique"] = df_perimetre["Code géographique"].astype(str)

        # Vérifier que les colonnes 'IRIS' existent dans les deux DataFrames
        if "IRIS" in new_df.columns and "IRIS" in df_perimetre.columns:
            # Effectuer la jointure sur la colonne 'IRIS'
            new_df = new_df.merge(df_perimetre, how='left', on="IRIS")
        elif "Code géographique" in new_df.columns and "IRIS" in df_perimetre.columns:
            # Effectuer la jointure sur la colonne 'Code géographique' si 'IRIS' n'est pas disponible
            new_df = new_df.merge(df_perimetre, how='left', left_on="Code géographique", right_on="IRIS")

        # Insérer les colonnes du périmètre au début du DataFrame
        reordered_columns = insert_position(0, new_df.columns.tolist(), df_perimetre.columns.tolist())
        
        # Ajouter les colonnes supplémentaires dans l'ordre spécifié
        new_column_order = ordered_columns + [col for col in new_df.columns if col not in ordered_columns]

        # Vérifier si toutes les colonnes à réorganiser existent dans new_df
        missing_columns = [col for col in reordered_columns if col not in new_df.columns]
        if missing_columns:
            print(f"Les colonnes suivantes sont manquantes dans new_df: {missing_columns}")
            continue  # Passer à l'itération suivante du dictionnaire si des colonnes sont manquantes

        new_df = new_df[new_column_order]  # Réorganiser les colonnes selon reordered_columns

        # Supprimer les colonnes inutiles après la jointure
        if "IRIS" in new_df.columns and not "Code géographique" in new_df.columns:
            new_df = new_df.drop(columns=["Commune ou ARM", "Type d'IRIS", "Label de l'IRIS", "Libellé de l'IRIS", "IRIS"], errors='ignore')
        elif "Code géographique" in new_df.columns :
            new_df = new_df.drop(columns=["Code géographique", "Note de diffusion", "Commune ou ARM", "Libellé de l'IRIS", "IRIS"], errors='ignore')

        # Stocker le DataFrame résultant dans le dictionnaire final
        joined_dict[key] = new_df

    return joined_dict


"""
Fonction permettant de charger un fichier YAML contenant la correspondance entre les noms de fichiers et le nom que l'on souhaite utiliser dans le fichier final.
Paramètres :
- path : chemin du fichier YAML
Retourne :
- mapping : dictionnaire contenant les correspondances entre les noms de fichiers et le nom que l'on souhaite utiliser dans le fichier final
"""
def load_mapping(chemin_fichier) -> dict:
    try:
        with open(chemin_fichier, 'r',encoding='UTF-8') as fichier:
            donnees_yaml = yaml.safe_load(fichier)
        return donnees_yaml
    except FileNotFoundError:
        print("Le fichier spécifié n'a pas été trouvé.")
        return None
    except yaml.YAMLError as e:
        print("Erreur lors du chargement du fichier YAML:", e)
        return None


"""
Fonction permettant de charger les libellés des IRIS.
Retourne :
- libelles : pandas.DataFrame contenant les correspondances entre les IRIS et le libellé
"""
def load_iris_libelles():
    path = "data1/libelles_iris_roubaix.yml"
    with open(path, 'r', encoding="UTF-8") as stream:
        try:
            libelles = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)
    return libelles


def load_perimetre_mas() -> pd.DataFrame:
    path = "data1/Périmètres_MAS.csv"  # Chemin vers le fichier CSV
    # Lire le fichier CSV dans un DataFrame
    df_csv = pd.read_csv(path)
    # Renommer les colonnes selon la correspondance spécifiée
    df_csv = df_csv.rename(columns={
        "Libellé_IRIS": "Libellé de l'Iris",
        "Quartier": "Mairies de quartiers",
        "Centre_Social": "Centres sociaux",
        "Périmètre_NPNRU": "Périmètres NPNRU",
        "ContratVille2024": "Contrats de Ville 2024 (CDV)",
        "Cité_Educative": "Cités éducatives",
        "Grands_quartiers": "Grands quartiers",
    })

    return df_csv


"""
Fonction permetant de charger un fichier YAML contenant les superficies des IRIS.
Retourne :
- superficies : dictionnaire contenant les correspondances entre les IRIS et le libellé
"""
def load_superficies():
    path = "data1/superficies_iris_roubaix.yml"
    with open(path, 'r', encoding="UTF-8") as stream:
        try:
            superficies = yaml.safe_load(stream)
            # Assurez-vous que superficies est un dictionnaire et qu'on peut itérer dessus
            if isinstance(superficies, dict):
                # Arrondir chaque valeur numérique à 1 chiffre après la virgule
                for key, value in superficies.items():
                    if isinstance(value, (int, float)):  # Si la valeur est numérique
                        superficies[key] = round(value, 1)
        except yaml.YAMLError as exc:
            print(exc)
    return superficies


def get_mapped_name(file_name, mapping):
    for key in mapping:
        if key in file_name:
            return mapping[key]


"""
Fonction permettant d'extraire l'année d'un nom defichier INSEE.
Paramètres :
- file_name : nom du fichier INSEE
Retourne :
- année du fichier INSEE
"""
def extract_year(file_name):
    return re.search(r'\d{4}', file_name).group()


"""
Fonction permettant d'insérer une liste dans une autre liste à une position donnée.
Paramètres :
- position : position dans la liste dans laquelle on veut insérer la liste
- list1 : liste dans laquelle on veut insérer la liste
- list2 : liste à insérer dans la liste 1
Retourne :
- liste contenant la liste 1 et la liste 2
"""
def insert_position(position, list1, list2):
    return list1[:position] + list2 + list1[position:]
