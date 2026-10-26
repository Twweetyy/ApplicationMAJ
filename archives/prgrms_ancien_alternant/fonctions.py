from utils import *
import os
import pandas as pd
from tqdm import tqdm
from copy import copy
import numpy as np
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

def load_CSV_files(path):
    files = {}
    for file in tqdm(os.listdir(path)):
        if file.endswith(".csv") or file.endswith(".CSV"):
            df = pd.read_csv(path + "/" + file, sep=";", na_values=np.nan)
            # Appliquer round() sur les colonnes numériques
            # On peut utiliser select_dtypes pour récupérer uniquement les colonnes de type numérique
            numeric_columns = df.select_dtypes(include=['float64', 'int64']).columns
            df[numeric_columns] = df[numeric_columns].round(0)  # Arrondi à 0 chiffres après la virgule
            # Charger les libellés des IRIS et les superficies et les fusionner
            df = join_iris_libelles(df, load_iris_libelles())
            df = join_iris_superficies(df, load_superficies())
            files[file[:-4]] = df
    return files


"""
Fonction permettant de renommer les clés du dictionnaire de fichiers INSEE par des noms plus lisibles
Paramètres :
- files : dictionnaire contenant un objet pandas.DataFrame pour chaque fichier INSEE indexé par le nom du fichier sans l'extension
- YEARS : dictionnaire contenant l'année des fichiers INSEE 
Retourne :
- new_dict_of_files : dictionnaire contenant un objet pandas.DataFrame pour chaque fichier INSEE indexé par un nom plus lisible
"""
def rename_files(files):
    mapping = load_mapping("data1/files_names.yml")
    
    new_dict_of_files = copy(files)
    YEARS = {}
    for key in tqdm(files):
        
        # Si le mapping est un caractère du nom du fichier, renomme le fichier
        if any(substring in key for substring in mapping):
            
            new_dict_of_files[get_mapped_name(key, mapping)] = new_dict_of_files.pop(key)
            # Extrait l'année de la clé
            YEARS[get_mapped_name(key, mapping)] = extract_year(key)
    return new_dict_of_files, YEARS


"""
Fonction permettant de filtrer un dataframe à l'échelle d'une liste de code postaux passées en paramètre.
Paramètres :
- df : dataframe à filtrer
- cities : liste de villes sur lesquelles filtrer le dataframe
Retourne :
- new_df : dataframe filtré
"""
def filter_df(df: pd.DataFrame, cities = ["59512"]) -> pd.DataFrame:
    new_df = pd.DataFrame([], columns=df.columns)
    # Si le tableau a une colonne se nommant "COM", il l'utilise pour filtrer le tableau 
    if "COM" in df.columns:
        new_df = df[df["COM"].astype(str).isin(cities)]

    # Sinon, filtre le tableau avec la colonne "IRIS" ou "CODGEO" 
    elif "IRIS" in df.columns:
            for city in cities:
                temp_df = df[df["IRIS"].astype(str).str.startswith(city)]
                # Créer la colonne "CODGEO" avec la valeur de la ville
                temp_df["COM"] = city
                # Concatène les lignes de temp_df en new_df
                new_df = pd.concat([new_df, temp_df])
    elif "CODGEO" in df.columns:
            for city in cities:
                temp_df = df[df["CODGEO"].astype(str).str.startswith(city)]
                # Créer la colonne "CODGEO" avec la valeur de la ville
                temp_df["COM"] = city
                # Concatène les lignes de temp_df en new_df
                new_df = pd.concat([new_df, temp_df])              

                
    return new_df.reset_index(drop=True)


"""
Fonction pour nettoyer les valeurs numériques en supprimant les caractères non numériques,
tout en laissant les autres valeurs (non numériques) intactes.
Si la colonne est 'Code géographique' ou 'IRIS', les valeurs numériques sont arrondies à 0
puis converties en chaîne de caractères (sans la partie décimale).
"""
def clean_numeric_values(value, column_name=None):
    # Si la valeur est NaN, la laisser intacte
    if pd.isna(value):
        return value
    
    # Si la colonne est 'Code géographique' ou 'IRIS', arrondir les valeurs numériques et les convertir en str
    if column_name in ['CODGEO', 'IRIS']:
        # Si la valeur est numérique, arrondir à 0, supprimer la décimale, et convertir en str
        if isinstance(value, (int, float)):
            return str(int(value))  # Convertit en entier pour enlever la partie décimale
        else:
            return value  # Si ce n'est pas un nombre, la laisser inchangée
    
    # Si la valeur est déjà un nombre (int ou float), la renvoyer telle quelle
    if isinstance(value, (int, float)):
        return value

    # Si la valeur est une chaîne de caractères
    if isinstance(value, str):
        # Vérifier si la chaîne représente un nombre valide
        if value.replace('.', '', 1).isdigit() or (value.count('.') == 1 and value.replace('.', '', 1).isdigit()):
            # Nettoyer les caractères non numériques, en gardant uniquement les chiffres et le point
            cleaned_value = ''.join(filter(lambda x: x.isdigit() or x == '.', value))
            # Retourner la valeur nettoyée en float
            return float(cleaned_value)
        else:
            # Si ce n'est pas un nombre, laisser la valeur inchangée
            return value

    # Si c'est un autre type de valeur, la laisser telle quelle
    return value


"""
Remplace les occurrences de 'ns' et 'so' par NaN dans un DataFrame.
Paramètres:
dataframe (pandas.DataFrame): Le DataFrame à modifier.
Retourne:
pandas.DataFrame: Le DataFrame modifié avec les 'ns' remplacés par NaN.
"""
def modif_type(dataframe):
    # Remplace les 'ns' et 'so' par NaN
    dataframe.replace(['ns', 'so'], pd.NA, inplace=True)
    
    # Convertit les colonnes numériques en float en remplaçant les virgules par des points
    for col in dataframe.select_dtypes(include=['object']):
        if dataframe[col].str.contains(',').any():
            dataframe[col] = dataframe[col].str.replace(',', '.')

    # Utilise la fonction clean_numeric_values pour nettoyer les valeurs numériques
    # Applique clean_numeric_values sur chaque élément, mais en s'assurant de ne pas transformer les colonnes 'CODGEO' ou 'IRIS'
    dataframe = dataframe.applymap(lambda x: clean_numeric_values(x, column_name=None))

    return dataframe


"""
Cette fonction parcourt tous les DataFrames dans `roubaix_files` et nettoie automatiquement
les colonnes contenant 'CODGEO' ou 'IRIS' en supprimant les décimales et en les convertissant en chaînes.
Paramètres :
- roubaix_files : dict : Un dictionnaire de DataFrames.
Retourne :
- dict : Le dictionnaire avec les DataFrames nettoyés.
"""
def clean_codgeo_and_iris_all_dataframes(roubaix_files: dict) -> dict:
    # Parcourir chaque DataFrame dans le dictionnaire 'roubaix_files'
    for file_key, df in roubaix_files.items():
        # Trouver les colonnes contenant 'CODGEO' ou 'IRIS'
        columns_to_clean = [col for col in df.columns if 'CODGEO' in col or 'IRIS' in col]
        
        # Appliquer la transformation sur ces colonnes
        for col in columns_to_clean:
            if col in df.columns:
                # Nettoyer la colonne en enlevant les décimales et en convertissant en str
                df[col] = df[col].apply(lambda x: str(int(x)) if isinstance(x, (int, float)) else x)
    
    return roubaix_files


"""
Fonction permettant de renommer les colonnes des fichiers par des noms compréhensibles à partir d'un dictionnaire de variables
Paramètres :
- files : dictionnaire contenant les dataframes des fichiers INSEE
Retourne :
- new_files : dictionnaire contenant les dataframes des fichiers INSEE avec colonnes renommées
"""
def rename_columns(files):
    new_files = {}
    #Pour chaque fichier, on renomme les colonnes
    for name, file in tqdm(files.items()):
        
        #Booléen pour savoir si on a affaire à un fichier Revenu
        fichier_revenu = name.upper().startswith("REV")
        #Booléen pour savoir si on a affaire à un fichier Population, Activité des Résidents, Formation, Ménages ou Logements
        fichier_population = name.upper().startswith("ACT") or name.upper().startswith("COU") \
                            or name.upper().startswith("DIP") or name.upper().startswith("POP") \
                            or name.upper().startswith("LOG") or name.upper().startswith("RPLS")
        
        # Copie du DataFrame pour effectuer les modifications
        modified_file = file.copy()
        print(modified_file.columns)
        
        # Renommer les colonnes pour les fichiers Revenu
        if fichier_revenu == True:
            
            columns = [x[0] for x in modified_file.columns[1:].str.rsplit("_", n=1)]

            for j, column in enumerate(columns):
                if column not in ["LIBIRIS", 'COM', "LIBCOM", "Superficie en km²", "Population 2006"]:
                    columns[j] += "_" + str(j)
            columns.insert(0, "IRIS")
            modified_file.columns = columns
            columns = [x[-1] for x in modified_file.columns[5:].str.rsplit("_", n=1)]
            columns = insert_position(0, columns, ['IRIS', 'COM', 'TYP_IRIS', 'MODIF_IRIS', 'LAB_IRIS'])
      
            # Renommer les colonnes à partir du dictionnaire de variables
            variable_dictionnary = load_mapping("data1/dictionnaire_variables.yml")
            for i in range(len(modified_file.columns)):
                if modified_file.columns[i] in variable_dictionnary:
                    modified_file.columns.values[i] = variable_dictionnary[modified_file.columns[i]]
            
            # Afficher les colonnes après le renommage
            #print(f"\nColonnes après renommage pour {name}: {modified_file.columns}")

        # Renommer les colonnes pour les fichiers Population, Activité des Résidents, Formation, Ménages ou Logements
        elif fichier_population:
            if name.upper().startswith("LOG") == True:
                columns = [x[-1] for x in modified_file.columns[4:].str.rsplit("_", n=1)]
            
                columns = insert_position(0, columns, ['IRIS', 'COM', 'TYP_IRIS','LAB_IRIS'])
                df=[]
                for i in range(len(columns)):
                    #print(columns[i])
                    if columns[i] in df :
                        index = 1
                        while f"{columns[i]} { index}" in df :
                            index += 1
                       # print("\n",i)
                        columns[i]=f"{columns[i]} { index}"
                        #print("\n",columns[i])
                        df.append(columns[i])
                        
                    else :
                        df.append(columns[i])
                        
                modified_file.columns = df
                
                # Afficher les colonnes avant le renommage
                #print(f"\nColonnes avant renommage pour {name}: {modified_file.columns}")
                
                # Renommer les colonnes à partir du dictionnaire de variables
                variable_dictionnary = load_mapping("data1/dictionnaire_variables_LOG.yml")
                for i in range(len(modified_file.columns)):
                    if modified_file.columns[i] in variable_dictionnary:
                        modified_file.columns.values[i] = variable_dictionnary[modified_file.columns[i]]
                
                # Afficher les colonnes après le renommage
                #print(f"\nColonnes après renommage pour {name}: {modified_file.columns}")
                
        
            elif name.upper().startswith("COU") == True:
               
                columns = []

                for col in modified_file.columns[4:]:
                    parts = col.rsplit('_', maxsplit=2)

                    if len(parts) > 1:
                        part_before = parts[-2]
                        part_before_upper = part_before.upper()
                        part_after = parts[-1]

                        # Si type GSECxx
                        if re.match(r'^GSEC\d+$', part_before_upper):
                            extracted = part_before

                        # Si ce qui suit n'est pas numérique → on le garde
                        elif not part_after.isdigit():
                            extracted = part_after

                        # Si avant contient lettres + chiffres → on garde avant
                        elif re.match(r'.*[A-Za-z]+.*\d+', part_before):
                            extracted = part_before

                        # Sinon → valeur après
                        else:
                            extracted = part_after

                    else:
                        extracted = parts[-1]

                    columns.append(extracted)


                # --- INSERTION DES 4 COLONNES EXACTEMENT COMME TON CODE -----------

                columns = insert_position(0, columns, ['IRIS', 'COM', 'TYP_IRIS','LAB_IRIS'])


                # --- DÉDOUBLONNAGE EXACTEMENT COMME TON CODE -----------------------

                df = []

                for i in range(len(columns)):
                    if columns[i] in df:
                        index = 1
                        while f"{columns[i]} {index}" in df:
                            index += 1

                        columns[i] = f"{columns[i]} {index}"
                        df.append(columns[i])
                    else:
                        df.append(columns[i])


                # --- APPLICATION DES NOUVEAUX NOMS -------------------------------

                modified_file.columns = df

                # Afficher les colonnes avant le renommage
                # print(f"\nColonnes avant renommage pour {name}: {modified_file.columns}")

                # Renommer les colonnes à partir du dictionnaire de variables
                variable_dictionnary = load_mapping("data1/dictionnaire_variables_COU.yml")  # ou POP.yml selon ton cas

                for i in range(len(modified_file.columns)):
                    if modified_file.columns[i] in variable_dictionnary:
                        modified_file.columns.values[i] = variable_dictionnary[modified_file.columns[i]]

                # print(f"\nColonnes après renommage pour {name}: {modified_file.columns}")

                            
                            
            
            elif name.upper().startswith("DIP")== True:
               
                columns = [x[-1] for x in modified_file.columns[4:].str.rsplit("_", n=1)]
            
                columns = insert_position(0, columns, ['IRIS', 'COM', 'TYP_IRIS','LAB_IRIS'])
                df=[]
                for i in range(len(columns)):
                    #print(columns[i])
                    if columns[i] in df :
                        index = 1
                        while f"{columns[i]} { index}" in df :
                            index += 1
                       # print("\n",i)
                        columns[i]=f"{columns[i]} { index}"
                        #print("\n",columns[i])
                        df.append(columns[i])
                        
                    else :
                        df.append(columns[i])
                        
                modified_file.columns = df
                
                # Afficher les colonnes avant le renommage
                #print(f"\nColonnes avant renommage pour {name}: {modified_file.columns}")
                
                # Renommer les colonnes à partir du dictionnaire de variables
                variable_dictionnary = load_mapping("data1/dictionnaire_variables_DIP.yml")
                for i in range(len(modified_file.columns)):
                    if modified_file.columns[i] in variable_dictionnary:
                        modified_file.columns.values[i] = variable_dictionnary[modified_file.columns[i]]
                
                # Afficher les colonnes après le renommage
                #print(f"\nColonnes après renommage pour {name}: {modified_file.columns}")
   
                
            elif name.upper().startswith("POP")== True:
              
                columns = []

                # --- EXTRACTION AMÉLIORÉE DIRECTEMENT DANS LA BOUCLE -----------------------

                for col in modified_file.columns[4:]:
                    parts = col.rsplit('_', maxsplit=2)

                    if len(parts) > 1:
                    
                        part_before = parts[-2]
                        part_before_upper = part_before.upper()
                        part_after = parts[-1]

                        # Si type GSECxx
                        if re.match(r'^GSEC\d+$', part_before_upper):
                            extracted = part_before

                        # Si ce qui suit n'est pas numérique → on le garde
                        elif not part_after.isdigit():
                            extracted = part_after

                        # Si avant contient lettres + chiffres → on garde avant
                        elif re.match(r'.*[A-Za-z]+.*\d+', part_before):
                            extracted = part_before

                        # Sinon → valeur après
                        else:
                            extracted = part_after

                    else:
                        extracted = parts[-1]

                    columns.append(extracted)


                # --- INSERTION DES 4 COLONNES DÉBUT EXACTEMENT COMME TON CODE -------------

                columns = insert_position(0, columns, ['IRIS', 'COM', 'TYP_IRIS','LAB_IRIS'])


                # --- DÉDOUBLONNAGE EXACTEMENT COMME TON CODE ------------------------------

                df = []

                for i in range(len(columns)):
                    if columns[i] in df:
                        index = 1
                        while f"{columns[i]} {index}" in df:
                            index += 1

                        columns[i] = f"{columns[i]} {index}"
                        df.append(columns[i])
                    else:
                        df.append(columns[i])


                # --- APPLICATION FINALE ----------------------------------------------------

                modified_file.columns = df

               
               # Afficher les colonnes avant le renommage
               #print(f"\nColonnes avant renommage pour {name}: {modified_file.columns}")
               
               # Renommer les colonnes à partir du dictionnaire de variables
                variable_dictionnary = load_mapping("data1/dictionnaire_variables_POP.yml")
                for i in range(len(modified_file.columns)):
                   if modified_file.columns[i] in variable_dictionnary:
                       modified_file.columns.values[i] = variable_dictionnary[modified_file.columns[i]]
               
               # Afficher les colonnes après le renommage
               #print(f"\nColonnes après renommage pour {name}: {modified_file.columns}")
               
            elif name.upper().startswith("ACT") ==True:
             
                columns = []

                for col in modified_file.columns[4:]:
                    # Cas GSEC : STAT_GSEC13_23 → GSEC13
                    if "GSEC" in col:
                        # on coupe après GSEC puis on enlève le suffixe _xx
                        gsec_part = col.split("GSEC")[1]      # ex: "13_23"
                        gsec_num = gsec_part.split("_")[0]    # ex: "13"
                        columns.append(f"GSEC{gsec_num}")
                    else:
                        # comportement initial
                        columns.append(col.rsplit("_", 1)[-1])


                columns = insert_position(0, columns, ['IRIS', 'COM', 'TYP_IRIS','LAB_IRIS'])
                df=[]
                for i in range(len(columns)):
                    if columns[i] in df :
                        index = 1
                        while f"{columns[i]} { index}" in df :
                            index += 1
                        print("\n",i)
                        columns[i]=f"{columns[i]} { index}"
                        print("\n",columns[i])
                        df.append(columns[i])
                        
                    else :
                        df.append(columns[i])
                        
                modified_file.columns = df
                
                # Afficher les colonnes avant le renommage
                #print(f"\nColonnes avant renommage pour {name}: {modified_file.columns}")
                
                # Renommer les colonnes à partir du dictionnaire de variables
                variable_dictionnary = load_mapping("data1/dictionnaire_variables_ACT.yml")
                for i in range(len(modified_file.columns)):
                    if modified_file.columns[i] in variable_dictionnary:
                        modified_file.columns.values[i] = variable_dictionnary[modified_file.columns[i]]
                
                # Afficher les colonnes après le renommage
                #print(f"\nColonnes après renommage pour {name}: {modified_file.columns}")
        
        # Renommer les colonnes à partir du dictionnaire de variables
        variable_dictionnary = load_mapping("data1/dictionnaire_variables.yml")
        for i in range(len(modified_file.columns)):
            if modified_file.columns[i] in variable_dictionnary:
                modified_file.columns.values[i] = variable_dictionnary[modified_file.columns[i]]

        # Afficher les colonnes après le renommage
        #print(f"Colonnes après renommage pour {name}: {modified_file.columns}")

        # Supprimer les colonnes en double par rapport au mapping des variables
        unique_columns = list(dict.fromkeys(modified_file.columns))
        modified_file = modified_file[unique_columns]

        # Ajouter le fichier modifié au dictionnaire à renvoyer
        new_files[name] = modified_file

    return new_files


def ajouter_nouvelles_colonnes(fichiers, chemin_yaml):
    with open(chemin_yaml, "r", encoding="UTF-8") as file:
        yaml_ = yaml.safe_load(file)

    for key in yaml_:
        expression = yaml_[key]["expression"]
        column_to_calculate = key
        df_name = yaml_[key]["df"]
        var1 = yaml_[key]["var1"]
        var2 = yaml_[key]["var2"]
        var3 = yaml_[key]["var3"]
        var4 = yaml_[key]["var4"]
        
        try:
            # Vérifier et supprimer les doublons dans les colonnes
            fichiers[df_name] = fichiers[df_name].loc[:, ~fichiers[df_name].columns.duplicated()]
            # Réinitialiser les indices en cas de doublons dans les indices
            fichiers[df_name] = fichiers[df_name].reset_index(drop=True)

            fichiers[df_name][column_to_calculate] = round(pd.eval(expression, engine='python', parser='pandas', 
                        local_dict={'files': fichiers, 'df': df_name, 'var1': var1, 'var2': var2, 'var3': var3, 'var4': var4, 'np': np}),1)
        except KeyError as e:
            print(f"KeyError in {key} for {var1} : {e}")
            continue
        except TypeError as e2:
            print(f"TypeError : {e2}", var1, var2)
            continue
        except ZeroDivisionError as e3:
            print(f"ZeroDivisionError : {e3} between {var1} and {var2}.")
            print("Replacing the value to `np.nan` and proceeding.")
            fichiers[df_name][column_to_calculate] = 100 * fichiers[df_name][var1].div(fichiers[df_name][var2].replace(0, np.nan))

    return fichiers

def exporter_dictionnaire_en_excel(fichiers, chemin_fichier:str):
    # Créer un writer pour le fichier Excel
    with pd.ExcelWriter(chemin_fichier, engine='openpyxl') as writer:
        # Parcourir chaque DataFrame dans le dictionnaire
        for nom_df, df in fichiers.items():
            # Écrire le DataFrame sur une feuille de calcul avec le nom du DataFrame
            df.to_excel(writer, sheet_name=nom_df, index=False)
    print(f"Fichier Excel enregistré sous {chemin_fichier}")

def mise_en_forme_excel(chemin_fichier: str):
    # Mise en forme de l'excel

    # Charger le fichier Excel existant
    wb = openpyxl.load_workbook(chemin_fichier)
    
    for ws in wb.worksheets:
        # 1. Insérer une ligne vide au début pour laisser la ligne 1 vide
        ws.insert_rows(1, amount=1)  # Décale tout le contenu vers le bas d'une ligne

        # 2. Déplacer les titres (ligne 1) vers la ligne 2
        for col_idx, cell in enumerate(ws[1], start=1):
            ws.cell(row=2, column=col_idx, value=cell.value)

        # 3. Vider la première ligne (ligne 1) si vous le souhaitez
        for col_idx in range(1, len(ws[1]) + 1):  # effacer les valeurs de la première ligne
            ws.cell(row=1, column=col_idx, value=None)

        # 4. Mettre "Total" dans la cellule H1
        ws.cell(row=1, column=7, value="Total")

        # 5. Initialiser une variable gras
        bold_font = Font(bold=True)

        # 6. Calculer les sous-totaux pour les colonnes à partir de I (colonne 9) avec la somme (SUM)
        for col_idx in range(8, ws.max_column + 1):  # Commencer à la colonne I (colonne 9)
            last_row = ws.max_row
            # Utiliser la fonction SUM pour la colonne correspondante (commence à la ligne 3)
            ws.cell(row=1, column=col_idx, value=f"=SUBTOTAL(9,{get_column_letter(col_idx)}3:{get_column_letter(col_idx)}{last_row})")
            ws.cell(row=1, column=col_idx).font = bold_font
        
        # 7. Appliquer la mise en forme aux données existantes dans l'Excel à partir de la ligne 3
        for row_idx in range(3, ws.max_row + 1):  # Parcourir les lignes à partir de la ligne 3
            for col_idx in range(1, ws.max_column + 1):  # Parcourir les colonnes
                cell = ws.cell(row=row_idx, column=col_idx)
                # Appliquer des formats conditionnels si nécessaire
                cell.font = Font(bold=False)  # Enlever le gras pour les autres cellules
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # 8. Réinitialiser la ligne 2 à un format normal (sans gras)
        for col_idx in range(1, len(ws[2]) + 1):
            ws.cell(row=2, column=col_idx).font = Font(bold=False)  # Assurez-vous que la ligne 2 n'est pas en gras

        # 9. Appliquer le gras à toutes les lignes de A à H (y compris la ligne 1)
        for row_idx in range(1, ws.max_row + 1):  # Commencer à la ligne 1 et aller jusqu'à la dernière ligne
            for col_idx in range(1, 8):  # de la colonne A (1) à H (8)
                ws.cell(row=row_idx, column=col_idx).font = bold_font

        # 10. Appliquer un format spécifique à la ligne 2 : hauteur, alignement, retour à la ligne
        ws.row_dimensions[2].height = 80  # Hauteur de la ligne 2
        # Définir la largeur des colonnes, en se basant sur les titres de la ligne 2
        for col_idx in range(1, len(ws[2]) + 1):
            col_letter = get_column_letter(col_idx)
            if ws.cell(row=2, column=col_idx).value == "Libellé de l'Iris":
                ws.column_dimensions[col_letter].width = 24  # Largeur spécifique pour la colonne "Libellé de l'Iris"
            else:
                ws.column_dimensions[col_letter].width = 15  # Largeur par défaut pour les autres colonnes

        # ** Trouver la colonne de "Superficie en km²" **
        col_superficie = None
        for col_idx, cell in enumerate(ws[2], start=1):
            if cell.value == "Superficie en km²":
                col_superficie = col_idx
                break

        if col_superficie is None:
            raise ValueError("La colonne 'Superficie en km²' n'a pas été trouvée dans les titres.")

        # Appliquer l'alignement centré et le retour à la ligne automatique sur toutes les cellules de la ligne 1 et 2
        for col_idx in range(1, len(ws[3]) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.alignment = Alignment(horizontal="center")
            cell.font = Font(color="00B050", bold=True)  # Appliquer une couleur verte à la ligne 1
            cell = ws.cell(row=2, column=col_idx)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)  # Centrer et retour à la ligne

        # Récupérer l'index de la dernière colonne de la feuille Excel
        last_col_idx = ws.max_column

        # Définir une bordure grise (tout autour de la cellule)
        gray_border = Border(
            left=Side(border_style="thin", color="BFBFBF"),  # Bordure grise à gauche
            right=Side(border_style="thin", color="BFBFBF"),  # Bordure grise à droite
            top=Side(border_style="thin", color="BFBFBF"),  # Bordure grise en haut
            bottom=Side(border_style="thin", color="BFBFBF")  # Bordure grise en bas
        )

        # Appliquer les couleurs de fond en fonction de la ligne et de la colonne
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=last_col_idx):
            for cell in row:
                # Assurez-vous que vous travaillez avec la ligne correcte (1 pour les titres, 2 pour les sous-titres, etc.)
                if cell.row == 1:
                    # Appliquer une couleur verte sur les colonnes de 7 à 24
                    if 7 <= cell.column <= ws.max_column:
                        cell.fill = PatternFill(start_color="EBF1DE", end_color="EBF1DE", fill_type="solid")  # Fond vert
                elif cell.row == 2:
                    # Appliquer une couleur grise sur les premières colonnes et bleue sur les autres
                    if cell.column < 8:
                        cell.fill = PatternFill(start_color="BFBFBF", end_color="BFBFBF", fill_type="solid")  # Fond gris
                    elif cell.column < col_superficie:
                        cell.fill = PatternFill(start_color="91DEFF", end_color="91DEFF", fill_type="solid")  # Fond bleu
                    else:
                        cell.fill = PatternFill(start_color="F8CBAD", end_color="F8CBAD", fill_type="solid")  # Fond orange
                else:
                    # Appliquer une couleur grise pour les autres lignes
                    if cell.column < 8:
                        cell.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")  # Fond gris
                cell.border = gray_border
        
        variable_dictionnary = load_mapping("data1/info_pages.yml")
        if ws.title in variable_dictionnary:
            ws.cell(row=1, column=1, value=variable_dictionnary[ws.title])
            ws.cell(row=1, column=1).alignment = Alignment(horizontal="left")
            ws.cell(row=1, column=1).font = Font(color="800000", bold=True)

    # 11. Déplacement de la feuille POP 2021 et Rajout de la feuille PETITE ENFANCE 2021
    # Obtenir la feuille que vous souhaitez déplacer
    sheet_to_move = wb['POP 2022']
    # Obtenir la position actuelle de la feuille
    current_index = wb.sheetnames.index(sheet_to_move.title)
    # Déplacer la feuille à la nouvelle position (par exemple, à la première position)
    new_index = 0
    wb._sheets.insert(new_index, wb._sheets.pop(current_index))

    workbook = openpyxl.load_workbook('Dossier_enfance/tab_mas_age_revolu_enfants_roubaix.xlsx')
    # Obtenir la feuille que vous souhaitez déplacer
    source_sheet = workbook['PETITE ENFANCE 2022']
    # Copier la feuille source dans le fichier de destination
    wb.create_sheet(title=source_sheet.title)
    destination_sheet = wb[source_sheet.title]
    # Copier les cellules et leur mise en forme sans utiliser StyleProxy
    for row in source_sheet.iter_rows():
        for cell in row:
            new_cell = destination_sheet.cell(row=cell.row, column=cell.col_idx, value=cell.value)

            # Si la cellule a un style, on copie les propriétés de manière explicite
            if cell.has_style:
                # Copier la police (font)
                if cell.font:
                    new_cell.font = Font(
                        name=cell.font.name,
                        bold=cell.font.bold,
                        italic=cell.font.italic,
                        vertAlign=cell.font.vertAlign,
                        underline=cell.font.underline,
                        strike=cell.font.strike,
                        color=cell.font.color,
                        size=cell.font.size,
                        family=cell.font.family,
                        charset=cell.font.charset,
                        scheme=cell.font.scheme
                    )

                # Copier la bordure (border)
                if cell.border:
                    new_cell.border = Border(
                        left=cell.border.left,
                        right=cell.border.right,
                        top=cell.border.top,
                        bottom=cell.border.bottom,
                        diagonal=cell.border.diagonal,
                        diagonal_direction=cell.border.diagonal_direction,
                        outline=cell.border.outline,
                        vertical=cell.border.vertical,
                        horizontal=cell.border.horizontal
                    )

                # Copier le remplissage (fill)
                if cell.fill:
                    new_cell.fill = PatternFill(
                        start_color=cell.fill.start_color,
                        end_color=cell.fill.end_color,
                        fill_type=cell.fill.fill_type
                    )

                # Copier l'alignement (alignment)
                if cell.alignment:
                    new_cell.alignment = Alignment(
                        horizontal=cell.alignment.horizontal,
                        vertical=cell.alignment.vertical,
                        text_rotation=cell.alignment.text_rotation,
                        wrap_text=cell.alignment.wrap_text,
                        shrink_to_fit=cell.alignment.shrink_to_fit,
                        indent=cell.alignment.indent
                    )

    # Obtenir la feuille que vous souhaitez déplacer
    sheet_to_move = wb['PETITE ENFANCE 2022']
    # Obtenir la position actuelle de la feuille
    current_index = wb.sheetnames.index(sheet_to_move.title)
    # Déplacer la feuille à la nouvelle position (par exemple, à la première position)
    new_index = 7
    wb._sheets.insert(new_index, wb._sheets.pop(current_index))

    # 12. Sauvegarder le fichier Excel modifié
    wb.save(chemin_fichier)