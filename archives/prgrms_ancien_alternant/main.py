#from re import T
from fonctions import *

# Lancement du code principal, chargement des fichiers, appel à la fonction dans fonctions
print("Chargement des fichiers INSEE...")
files = load_CSV_files(input("Chemin du dossier des fichiers INSEE : "))

# Renommage des noms de fichiers sur les feuilles excel, appel à la fonction dans fonctions
print("Renommage des fichiers INSEE...")
files, YEARS = rename_files(files)
files2 = files.copy()
for file in files.keys():
    for YEAR in YEARS.items():
        if file==YEAR[0]:
            files2[file+' '+YEAR[1]] = files2.pop(file)



# Filtre des données selon le code postale de roubaix, appel à la fonction dans fonctions
print("Filtrage des données sur Roubaix...")
roubaix_files = {}
for name, file in tqdm(files2.items()):
    roubaix_files[name] = modif_type(filter_df(file, ["59512"]))

# Appliquer la fonction de nettoyage sur tous les DataFrames dans roubaix_files
roubaix_files = clean_codgeo_and_iris_all_dataframes(roubaix_files)

# Renommage des noms de colonnes de fichiers sur les feuilles excel, appel à la fonction dans fonctions
print("Renommage des colonnes...")
roubaix_files=rename_columns(roubaix_files)

'''
#print(f"Type de roubaix_files : {type(roubaix_files)}")
for key, df in roubaix_files.items():
    print(f"Clé : {key}, Type de valeur : {type(df)}")
    print(roubaix_files[key].head())
'''

roubaix_files=join_iris_perimetre_mas(roubaix_files, load_perimetre_mas())

# Ajout de certaines colonnes en fonction d'un mapping, appel à la fonction dans fonctions
fichiers = ajouter_nouvelles_colonnes(roubaix_files, 'data1/calculated_columns.yml')

# Extraction du fichier en fonction d'un titre et dans un fichier de destination, appel à la fonction dans fonctions
chemin_fichier_excel = 'TAB_BDDMAS_INSEE2022_Tout_perimetre.xlsx'
exporter_dictionnaire_en_excel(fichiers, chemin_fichier_excel)

mise_en_forme_excel(chemin_fichier_excel)


