import os
import re
import pandas as pd
import numpy as np
import yaml
from tqdm.auto import tqdm

def load_mapping(chemin_fichier: str) -> dict:
    """Charge un dictionnaire YAML (variables, renommages, etc.)."""
    try:
        with open(chemin_fichier, 'r', encoding='UTF-8') as fichier:
            return yaml.safe_load(fichier) or {}
    except FileNotFoundError:
        print(f"Attention : Le fichier {chemin_fichier} est introuvable.")
        return {}


def _normaliser_identifiant(nom: str) -> str:
    return str(nom).strip().casefold()


def _normaliser_nom_fichier(nom: str) -> str:
    sans_annee = re.sub(r"\d{4}", "", str(nom).casefold())
    return re.sub(r"[^a-z0-9]", "", sans_annee)


def _cle_nom_fichier_meta(nom_fichier: str) -> str:
    nom_base = os.path.splitext(os.path.basename(nom_fichier))[0]
    prefixe = nom_base.casefold()
    if prefixe.startswith("meta_") or prefixe.startswith("data_"):
        nom_base = nom_base[5:]
    return _normaliser_nom_fichier(nom_base)


def _trouver_fichier_meta(fichier: str, dossiers: list[str]) -> str | None:
    cle_source = _cle_nom_fichier_meta(fichier)
    for dossier in dossiers:
        if not os.path.isdir(dossier):
            continue
        for nom in os.listdir(dossier):
            if not nom.casefold().startswith("meta_") or not nom.casefold().endswith(".csv"):
                continue
            if _cle_nom_fichier_meta(nom) == cle_source:
                return os.path.join(dossier, nom)
    return None


def _normaliser_modalite(valeur) -> str:
    texte = str(valeur).strip()
    try:
        nombre = float(texte.replace(",", "."))
        if nombre.is_integer():
            return str(int(nombre))
    except ValueError:
        pass
    return texte.casefold()


def _charger_metadonnees(
    chemin: str | None,
    colonnes_variables: list[str] | None = None,
) -> tuple[dict, dict]:
    if not chemin:
        return {}, {}
    try:
        metadonnees = pd.read_csv(chemin, sep=";", dtype=str, encoding="utf-8-sig")
    except (OSError, pd.errors.ParserError, UnicodeError):
        return {}, {}
    metadonnees.columns = [str(colonne).strip().upper() for colonne in metadonnees.columns]
    if not {"COD_VAR", "LIB_VAR"}.issubset(metadonnees.columns):
        return {}, {}

    metadonnees["COD_VAR"] = metadonnees["COD_VAR"].astype("string").str.strip()
    metadonnees["CODE_NORMALISE"] = metadonnees["COD_VAR"].map(_normaliser_identifiant)
    if colonnes_variables is not None:
        codes_requis = {_normaliser_identifiant(colonne) for colonne in colonnes_variables}
        metadonnees = metadonnees[metadonnees["CODE_NORMALISE"].isin(codes_requis)]

    variables = metadonnees[["CODE_NORMALISE", "LIB_VAR"]].dropna().drop_duplicates("CODE_NORMALISE")
    libelles = {
        code: libelle.strip()
        for code, libelle in zip(variables["CODE_NORMALISE"], variables["LIB_VAR"])
        if str(libelle).strip()
    }

    colonnes_modalites = {"COD_MOD", "LIB_MOD", "TYPE_VAR"}
    modalites = {}
    if colonnes_modalites.issubset(metadonnees.columns):
        variables_a_modalites = metadonnees[
            metadonnees["TYPE_VAR"].astype("string").str.upper().eq("CHAR")
            & ~metadonnees["CODE_NORMALISE"].isin({"iris", "codgeo", "com"})
        ][["CODE_NORMALISE", "COD_MOD", "LIB_MOD"]].dropna()
        modalites = {
            (code, _normaliser_modalite(modalite)): libelle.strip()
            for code, modalite, libelle in zip(
                variables_a_modalites["CODE_NORMALISE"],
                variables_a_modalites["COD_MOD"],
                variables_a_modalites["LIB_MOD"],
            )
            if str(libelle).strip()
        }
    return libelles, modalites


def nettoyage_valeurs_insee(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoie les DataFrames Insee :
    - Remplace 'ns' (non significatif) et 'so' (sans objet) par du vide (NaN).
    - Convertit les virgules en points pour les décimales.
    - Transforme les colonnes numériques en float/int.
    """
    # Remplacement des valeurs aberrantes Insee
    df = df.replace(['ns', 'so'], np.nan)
    
    # Correction des virgules européennes en points décimaux
    for col in df.select_dtypes(include=['object']).columns:
        if col not in ['IRIS', 'CODGEO', 'COM', 'TYP_IRIS', 'LAB_IRIS']:
            if df[col].str.contains(',', na=False).any():
                df[col] = df[col].str.replace(',', '.')
            
            # Tentative de conversion en numérique
            try:
                df[col] = pd.to_numeric(df[col])
            except ValueError:
                pass # Si ça échoue, c'est du vrai texte, on laisse.
                
    return df

def preparer_colonnes_thematiques(
    df: pd.DataFrame,
    theme: str,
    dict_vars: dict,
    libelles_metadonnees: dict | None = None,
    dict_vars_generiques: dict | None = None,
    modalites_metadonnees: dict | None = None,
) -> pd.DataFrame:
    """
    Reprend la logique de l'ancien script 'rename_columns' mais de façon optimisée.
    Gère les préfixes Insee et les déclinaisons complexes (GSEC).
    """
    nouveaux_noms = []
    colonnes_source = list(df.columns)
    colonnes_geo = ['IRIS', 'COM', 'TYP_IRIS', 'LAB_IRIS']
    
    for col in df.columns:
        if col in colonnes_geo:
            nouveaux_noms.append(col)
            continue
            
        # Logique spécifique selon le thème (Inspiré du code précédent)
        if theme in ['POP', 'COU']:
            parts = col.rsplit('_', maxsplit=2)
            if len(parts) > 1:
                part_before = parts[-2]
                part_before_upper = part_before.upper()
                part_after = parts[-1]
                
                if re.match(r'^GSEC\d+$', part_before_upper):
                    extracted = part_before
                elif not part_after.isdigit():
                    extracted = part_after
                elif re.match(r'.*[A-Za-z]+.*\d+', part_before):
                    extracted = part_before
                else:
                    extracted = part_after
            else:
                extracted = parts[-1]
            nouveaux_noms.append(extracted)
            
        elif theme == 'ACT':
            if "GSEC" in col:
                gsec_part = col.split("GSEC")[1]      
                gsec_num = gsec_part.split("_")[0]    
                nouveaux_noms.append(f"GSEC{gsec_num}")
            else:
                nouveaux_noms.append(col.rsplit("_", 1)[-1])
                
        elif theme in {"CAF", "CNAM", "DEFM", "RPLS", "REV"}:
            nouveaux_noms.append(col)
        else: # LOG, DIP, etc.
            nouveaux_noms.append(col.rsplit("_", 1)[-1])
            
    # Gestion des doublons de colonnes (Ex: POP H / POP F)
    noms_dedoublonnes = []
    for col in nouveaux_noms:
        if col in noms_dedoublonnes:
            index = 1
            while f"{col} {index}" in noms_dedoublonnes:
                index += 1
            noms_dedoublonnes.append(f"{col} {index}")
        else:
            noms_dedoublonnes.append(col)
            
    libelles_yaml = {
        _normaliser_identifiant(code): libelle
        for code, libelle in dict_vars.items()
    }
    libelles_metadonnees = libelles_metadonnees or {}
    libelles_generiques = {
        _normaliser_identifiant(code): libelle
        for code, libelle in (dict_vars_generiques or {}).items()
    }
    modalites_metadonnees = modalites_metadonnees or {}
    noms_finaux = [
        libelles_yaml.get(_normaliser_identifiant(nom))
        or libelles_metadonnees.get(_normaliser_identifiant(source))
        or libelles_metadonnees.get(_normaliser_identifiant(nom))
        or libelles_generiques.get(_normaliser_identifiant(nom))
        or nom
        for source, nom in zip(colonnes_source, noms_dedoublonnes)
    ]
    for source, nom_final in zip(colonnes_source, noms_finaux):
        code_variable = _normaliser_identifiant(source)
        correspondances = {
            _normaliser_modalite(valeur): modalites_metadonnees[(code_variable, _normaliser_modalite(valeur))]
            for valeur in df[source].dropna().unique()
            if (code_variable, _normaliser_modalite(valeur)) in modalites_metadonnees
        }
        if correspondances:
            df[source] = df[source].map(
                lambda valeur: correspondances.get(_normaliser_modalite(valeur), valeur)
                if not pd.isna(valeur)
                else valeur
            )
    df.columns = noms_finaux
    return df

def ingerer_donnees_thematiques(dossier_data: str, dossier_dicos: str) -> dict:
    """
    Fonction principale d'ingestion. Lit tous les CSV du dossier, 
    filtre sur Roubaix, nettoie et renomme les variables.
    Retourne un dictionnaire { 'POP 2022': DataFrame, ... }
    """
    dico_dataframes = {}
    
    # Récupération du mapping des noms (ex: 'base-ic-evol-struct-pop' -> 'POP')
    mapping_noms = load_mapping(os.path.join(dossier_dicos, "files_names.yml"))
    
    for fichier in os.listdir(dossier_data):
        if not fichier.lower().endswith(".csv") or fichier.lower().startswith("meta_"):
            continue

        nom_base = fichier[:-4]
        theme_identifie = None
        annee = re.search(r'\d{4}', nom_base).group() if re.search(r'\d{4}', nom_base) else "2022"
        nom_base_normalise = _normaliser_nom_fichier(nom_base)
        for cle_mapping, nom_cible in mapping_noms.items():
            cle_normalisee = _normaliser_nom_fichier(cle_mapping)
            if cle_mapping.casefold() in nom_base.casefold() or cle_normalisee in nom_base_normalise:
                theme_identifie = nom_cible
                break
        if not theme_identifie:
            continue

        chemin_complet = os.path.join(dossier_data, fichier)
        df_brut = pd.read_csv(
            chemin_complet,
            sep=";",
            dtype={'IRIS': str, 'CODGEO': str, 'CodGeo': str, 'COM': str, 'LAB_IRIS': str},
            low_memory=False,
        )

        colonne_code_iris = next(
            (colonne for colonne in df_brut.columns if colonne.casefold() in {"codgeo", "iris"}),
            None,
        )
        if colonne_code_iris and colonne_code_iris != "IRIS":
            df_brut = df_brut.rename(columns={colonne_code_iris: "IRIS"})

        # Filtrage strict sur Roubaix
        if "IRIS" in df_brut.columns:
            df_brut = df_brut[df_brut["IRIS"].str.startswith("59512", na=False)]
        elif "COM" in df_brut.columns:
            df_brut = df_brut[df_brut["COM"] == "59512"]

        df_brut = df_brut.reset_index(drop=True)
        df_propre = nettoyage_valeurs_insee(df_brut)
        colonnes_vides = [
            colonne
            for colonne in df_propre.columns
            if (df_propre[colonne].isna() | df_propre[colonne].astype("string").str.strip().eq("")).all()
        ]
        df_propre = df_propre.drop(columns=colonnes_vides)
        cle_finale = f"{theme_identifie} {annee}"
        print(f"Traitement du thème : {cle_finale}")

        prefixe_dico = theme_identifie.split(' ')[0]
        fichier_dico = os.path.join(dossier_dicos, f"dictionnaire_variables_{prefixe_dico}.yml")
        dictionnaire_generique = load_mapping(os.path.join(dossier_dicos, "dictionnaire_variables.yml"))
        if os.path.exists(fichier_dico):
            dict_vars = load_mapping(fichier_dico)
        else:
            dict_vars = {}
        chemin_meta = _trouver_fichier_meta(
            fichier,
            [os.path.join(dossier_dicos, "meta"), dossier_data, dossier_dicos],
        )
        libelles_metadonnees, modalites_metadonnees = _charger_metadonnees(
            chemin_meta,
            df_propre.columns.tolist(),
        )
        df_final = preparer_colonnes_thematiques(
            df_propre,
            prefixe_dico,
            dict_vars,
            libelles_metadonnees,
            dictionnaire_generique,
            modalites_metadonnees,
        )
        dico_dataframes[cle_finale] = df_final
            
    return dico_dataframes


def _estimer_nombre_lignes_csv(chemin_fichier: str, taille_echantillon: int = 2_000_000):
    """Estime les lignes d'un CSV depuis un petit échantillon du début du fichier."""
    taille_fichier = os.path.getsize(chemin_fichier)
    with open(chemin_fichier, "rb") as fichier:
        echantillon = fichier.read(taille_echantillon)

    fin_ligne = echantillon.rfind(b"\n") + 1
    if fin_ligne == 0:
        return None

    nombre_lignes = echantillon[:fin_ligne].count(b"\n")
    if nombre_lignes == 0:
        return None

    octets_par_ligne = fin_ligne / nombre_lignes
    return max(0, round(taille_fichier / octets_par_ligne) - 1)


def lire_individus_recensement(chemin_fichier: str, taille_bloc: int = 250_000):
    """Lit les variables enfants par blocs avec une estimation de progression."""
    if not os.path.exists(chemin_fichier):
        raise FileNotFoundError(f"Fichier de recensement introuvable : {chemin_fichier}")

    colonnes = ["IRIS", "AGEREV", "AGED", "IPONDI"]
    types = {
        "IRIS": str,
        "AGEREV": "float64",
        "AGED": "float64",
        "IPONDI": "float64",
    }
    total_estime = _estimer_nombre_lignes_csv(chemin_fichier)
    lecteur = pd.read_csv(
        chemin_fichier,
        sep=";",
        usecols=colonnes,
        dtype=types,
        chunksize=taille_bloc,
    )

    with tqdm(
        total=total_estime,
        desc="Lecture recensement enfants (lignes estimées)",
        unit="lignes",
        unit_scale=True,
        dynamic_ncols=True,
    ) as barre:
        for bloc in lecteur:
            barre.update(len(bloc))
            yield bloc