import os
import re
import unicodedata
import pandas as pd
import numpy as np
import yaml
from tqdm.auto import tqdm
from .lecture import compter_lignes, est_fichier_donnees, est_parquet, lire_entetes, lire_par_blocs, lire_table
from .colonnes_auto import (
    _cle_fichier,
    charger_cache,
    charger_millesimes_valides,
    charger_references,
    enregistrer_cache,
    enregistrer_millesimes_valides,
    millesime_a_traiter,
    resoudre_colonnes,
)

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
    texte = unicodedata.normalize("NFKD", str(nom).casefold())
    texte = "".join(caractere for caractere in texte if not unicodedata.combining(caractere))
    sans_annee = re.sub(r"\d{4}", "", texte)
    return re.sub(r"[^a-z0-9]", "", sans_annee)


def _cle_nom_fichier_meta(nom_fichier: str) -> str:
    nom_base = os.path.splitext(os.path.basename(nom_fichier))[0]
    prefixe = nom_base.casefold()
    if prefixe.startswith("meta_") or prefixe.startswith("data_"):
        nom_base = nom_base[5:]
    return _normaliser_nom_fichier(nom_base)


def _annee_nom_fichier(nom: str) -> str | None:
    correspondance = re.search(r"\d{4}", os.path.basename(nom))
    return correspondance.group() if correspondance else None


def trouver_fichier_meta(fichier: str, dossiers: list[str]) -> str | None:
    cle_source = _cle_nom_fichier_meta(fichier)
    annee_source = _annee_nom_fichier(fichier)
    candidats = []
    for dossier in dossiers:
        if not os.path.isdir(dossier):
            continue
        # Le dossier lui-même puis ses sous-dossiers directs (meta2022, meta2023...)
        dossiers_a_lire = [dossier] + [
            os.path.join(dossier, nom)
            for nom in sorted(os.listdir(dossier))
            if os.path.isdir(os.path.join(dossier, nom))
        ]
        for dossier_courant in dossiers_a_lire:
            for nom in sorted(os.listdir(dossier_courant)):
                nom_normalise = nom.casefold()
                if not nom_normalise.endswith(".csv"):
                    continue
                est_meta_source = nom_normalise.startswith("meta_") and _cle_nom_fichier_meta(nom) == cle_source
                est_meta_individus = (
                    cle_source == _normaliser_nom_fichier("FD_INDCVI")
                    and _cle_nom_fichier_meta(nom) == _normaliser_nom_fichier("varmod_indcvi")
                )
                if est_meta_source or est_meta_individus:
                    candidats.append(os.path.join(dossier_courant, nom))
    if not candidats:
        return None
    for candidat in candidats:
        if annee_source and _annee_nom_fichier(candidat) == annee_source:
            return candidat
    return candidats[0]


def _charger_iris_reference(dossier_dicos: str) -> set[str]:
    """Codes IRIS de Roubaix attendus (clés de grand_quartier.yml)."""
    chemin = os.path.join(dossier_dicos, "grand_quartier.yml")
    if not os.path.isfile(chemin):
        return set()
    return {str(code).strip() for code in load_mapping(chemin)}


def _iris_roubaix_presents(chemin: str, colonne: str, separateur: str) -> set[str]:
    """Lit uniquement la colonne IRIS, par blocs, et garde les codes de Roubaix."""
    presents = set()
    lecteur = lire_par_blocs(
        chemin,
        500_000,
        sep=separateur,
        usecols=[colonne],
        dtype={colonne: str},
        encoding="utf-8-sig",
        encoding_errors="replace",
    )
    for bloc in lecteur:
        valeurs = bloc[colonne].dropna().str.strip()
        # Codes IRIS à 9 caractères uniquement : la ligne « 59512 » (commune entière) est ignorée
        presents.update(valeurs[valeurs.str.fullmatch(r"59512\w{4}")])
    return presents


def _auditer_iris(rapport: dict, source: dict, chemin: str, entetes: list, separateur: str, iris_reference: set) -> None:
    """Ajoute un avertissement si le fichier n'a pas exactement les IRIS de Roubaix attendus."""
    if not iris_reference:
        return
    colonne_iris = next(
        (entete for entete in entetes if _normaliser_identifiant(entete) in {"iris", "codgeo"}),
        None,
    )
    if colonne_iris is None:
        return
    try:
        presents = _iris_roubaix_presents(chemin, colonne_iris, separateur)
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return
    manquants = sorted(iris_reference - presents)
    inconnus = sorted(presents - iris_reference)
    source["iris_roubaix"] = f"{len(presents & iris_reference)}/{len(iris_reference)}"
    if not manquants and not inconnus:
        return
    details = []
    if manquants:
        details.append(f"{len(manquants)} IRIS absent(s) : {', '.join(manquants)}")
    if inconnus:
        details.append(f"{len(inconnus)} IRIS inconnu(s) de grand_quartier.yml : {', '.join(inconnus)}")
    rapport["avertissements"].append({
        "code": "iris_incomplets",
        "fichier": source["fichier"],
        "theme": source.get("theme"),
        "manquants": manquants,
        "inconnus": inconnus,
        "message": f"{source['iris_roubaix']} IRIS de Roubaix trouvés. " + " ; ".join(details) + ".",
    })


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


def _identifier_theme_fichier(nom_fichier: str, mapping_noms: dict) -> tuple[str | None, str]:
    nom_base = os.path.splitext(os.path.basename(nom_fichier))[0]
    correspondance_annee = re.search(r"\d{4}", nom_base)
    annee = correspondance_annee.group() if correspondance_annee else "2022"
    nom_base_normalise = _normaliser_nom_fichier(nom_base)
    for cle_mapping, nom_cible in mapping_noms.items():
        cle_normalisee = _normaliser_nom_fichier(cle_mapping)
        if cle_mapping.casefold() in nom_base.casefold() or cle_normalisee in nom_base_normalise:
            return nom_cible, annee
    return None, annee


def analyser_fichiers_entree(dossier_data: str, dossier_dicos: str) -> dict:
    """Inspecte un lot d'entrée et retourne un rapport JSON-compatible sans traiter les lignes."""
    rapport = {
        "statut": "ok",
        "sources": [],
        "avertissements": [],
        "erreurs": [],
        "fichiers_ignores": [],
    }
    if not os.path.isdir(dossier_data):
        rapport["erreurs"].append({
            "code": "dossier_data_absent",
            "message": f"Dossier de données introuvable : {dossier_data}",
        })
        rapport["statut"] = "erreur"
        return rapport

    mapping_noms = load_mapping(os.path.join(dossier_dicos, "files_names.yml"))
    sources_par_theme = {}
    perimetre_trouve = False
    individus_trouves = False
    dossier_meta = os.path.join(dossier_dicos, "meta")
    iris_reference = _charger_iris_reference(dossier_dicos)

    for fichier in sorted(os.listdir(dossier_data)):
        if not est_fichier_donnees(fichier):
            continue

        cle_fichier = _normaliser_nom_fichier(os.path.splitext(fichier)[0])
        if cle_fichier == "perimetresmas":
            role = "perimetre"
            theme = None
            annee = None
        elif cle_fichier.startswith("fdindcvi"):
            role = "microdonnees_enfants"
            theme = None
            annee = re.search(r"\d{4}", fichier)
            annee = annee.group() if annee else None
        else:
            theme, annee = _identifier_theme_fichier(fichier, mapping_noms)
            role = "theme" if theme else None

        if role is None:
            rapport["fichiers_ignores"].append(fichier)
            rapport["avertissements"].append({
                "code": "fichier_non_reconnu",
                "fichier": fichier,
                "message": "Aucune entrée de files_names.yml ne reconnaît ce nom; le fichier sera ignoré.",
            })
            continue

        chemin = os.path.join(dossier_data, fichier)
        separateur = "," if role == "perimetre" else ";"
        try:
            entetes = lire_entetes(chemin, sep=separateur)
        except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeError) as erreur:
            rapport["erreurs"].append({
                "code": "csv_illisible",
                "fichier": fichier,
                "message": f"Impossible de lire l'en-tête du fichier : {erreur}",
            })
            continue

        entetes_normalisees = {_normaliser_identifiant(entete) for entete in entetes}
        meta_path = trouver_fichier_meta(fichier, [dossier_meta])
        source = {
            "fichier": fichier,
            "role": role,
            "theme": theme,
            "millesime": annee,
            "nombre_colonnes": len(entetes),
            "meta": os.path.basename(meta_path) if meta_path else None,
            "colonnes_non_documentees": [],
        }
        rapport["sources"].append(source)
        _auditer_iris(rapport, source, chemin, entetes, separateur, iris_reference)

        if role == "perimetre":
            perimetre_trouve = True
            if "iris" not in entetes_normalisees:
                rapport["erreurs"].append({
                    "code": "cle_iris_absente",
                    "fichier": fichier,
                    "message": "Le référentiel de périmètre doit contenir une colonne IRIS.",
                })
            continue

        if role == "microdonnees_enfants":
            individus_trouves = True
            colonnes_requises = {"iris", "agerev", "aged", "ipondi"}
            manquantes = sorted(colonnes_requises - entetes_normalisees)
            if manquantes:
                rapport["erreurs"].append({
                    "code": "colonnes_enfants_absentes",
                    "fichier": fichier,
                    "colonnes": manquantes,
                    "message": "Le fichier enfants ne contient pas toutes les colonnes utilisées par le calcul.",
                })
            if not meta_path:
                rapport["avertissements"].append({
                    "code": "meta_absente",
                    "fichier": fichier,
                    "message": "La méta varmod_indcvi n'a pas été trouvée.",
                })
            else:
                libelles_meta, _ = _charger_metadonnees(meta_path, list(colonnes_requises))
                colonnes_sans_meta = sorted(colonnes_requises - set(libelles_meta))
                if colonnes_sans_meta:
                    rapport["erreurs"].append({
                        "code": "colonnes_enfants_non_documentees",
                        "fichier": fichier,
                        "colonnes": colonnes_sans_meta,
                        "message": "La méta du fichier enfants ne documente pas toutes les colonnes requises.",
                    })
            continue

        if not entetes_normalisees.intersection({"iris", "codgeo", "com"}):
            rapport["erreurs"].append({
                "code": "cle_geographique_absente",
                "fichier": fichier,
                "theme": theme,
                "message": "Aucune colonne IRIS, CODGEO ou COM n'a été trouvée.",
            })

        if not meta_path:
            rapport["avertissements"].append({
                "code": "meta_absente",
                "fichier": fichier,
                "theme": theme,
                "message": "Aucune méta correspondante; les dictionnaires YAML seront utilisés en repli.",
            })
        else:
            try:
                entetes_meta = {
                    str(colonne).strip().upper()
                    for colonne in pd.read_csv(meta_path, sep=";", nrows=0, encoding="utf-8-sig").columns
                }
                if not {"COD_VAR", "LIB_VAR"}.issubset(entetes_meta):
                    raise ValueError("Les colonnes COD_VAR et LIB_VAR sont requises.")
                codes_meta = {
                    _normaliser_identifiant(code)
                    for code in pd.read_csv(
                        meta_path,
                        sep=";",
                        usecols=["COD_VAR"],
                        dtype=str,
                        encoding="utf-8-sig",
                    )["COD_VAR"].dropna()
                }
                prefixe_dico = theme.split(" ", 1)[0]
                chemins_dictionnaires = [
                    os.path.join(dossier_dicos, "dictionnaire_variables.yml"),
                    os.path.join(dossier_dicos, f"dictionnaire_variables_{prefixe_dico}.yml"),
                ]
                for chemin_dictionnaire in chemins_dictionnaires:
                    if not os.path.isfile(chemin_dictionnaire):
                        continue
                    codes_meta.update(
                        _normaliser_identifiant(code)
                        for code in load_mapping(chemin_dictionnaire)
                    )
                non_documentees = sorted(entete for entete in entetes if _normaliser_identifiant(entete) not in codes_meta)
                source["colonnes_non_documentees"] = non_documentees
                if non_documentees:
                    rapport["avertissements"].append({
                        "code": "colonnes_non_documentees",
                        "fichier": fichier,
                        "theme": theme,
                        "colonnes": non_documentees,
                        "message": "Ces colonnes n'ont pas de libellé dans la méta et seront conservées sous leur nom source.",
                    })
            except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeError, ValueError) as erreur:
                rapport["erreurs"].append({
                    "code": "meta_invalide",
                    "fichier": fichier,
                    "meta": os.path.basename(meta_path),
                    "message": f"La méta ne peut pas être utilisée : {erreur}",
                })

        sources_par_theme.setdefault(theme, []).append({"fichier": fichier, "millesime": annee})

    if not perimetre_trouve:
        rapport["erreurs"].append({
            "code": "perimetre_absent",
            "message": "Le fichier Périmètres_MAS (CSV ou Parquet) est requis pour joindre les données géographiques.",
        })
    if not sources_par_theme:
        rapport["erreurs"].append({
            "code": "aucun_theme_reconnu",
            "message": "Aucun fichier thématique ne correspond aux entrées de files_names.yml.",
        })
    if not individus_trouves:
        rapport["avertissements"].append({
            "code": "microdonnees_enfants_absentes",
            "message": "Le calcul de la petite enfance sera ignoré : aucun FD_INDCVI n'a été trouvé.",
        })

    for theme, sources in sources_par_theme.items():
        annees = {source["millesime"] for source in sources}
        if len(sources) > 1:
            rapport["erreurs"].append({
                "code": "versions_multiples_theme",
                "theme": theme,
                "fichiers": [source["fichier"] for source in sources],
                "message": "Plusieurs fichiers du même thème sont présents; le millésime à utiliser est ambigu.",
            })

    if rapport["erreurs"]:
        rapport["statut"] = "erreur"
    elif rapport["avertissements"]:
        rapport["statut"] = "attention"
    return rapport


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

def _vocabulaire_valide(dossier_dicos: str, millesimes_valides: dict, mapping_noms: dict) -> dict[str, list[str]]:
    """Noms de colonnes du classeur validé, par thème : codes de la méta du millésime validé
    passés dans preparer_colonnes_thematiques (dictionnaires YAML d'abord, puis méta),
    exactement comme lors du traitement validé. Sert de cible au module colonnes_auto."""
    dossier_meta = os.path.join(dossier_dicos, "meta")
    metas = []
    if os.path.isdir(dossier_meta):
        for dossier in [dossier_meta] + [os.path.join(dossier_meta, nom) for nom in sorted(os.listdir(dossier_meta))]:
            if os.path.isdir(dossier):
                metas += [os.path.join(dossier, nom) for nom in sorted(os.listdir(dossier)) if nom.casefold().endswith(".csv")]
    dictionnaire_generique = load_mapping(os.path.join(dossier_dicos, "dictionnaire_variables.yml"))
    vocabulaire = {}
    for cle_mapping, theme in mapping_noms.items():
        annee = millesimes_valides.get(theme)
        cle = _cle_fichier(cle_mapping)
        chemin_meta = next(
            (chemin for chemin in metas if annee and annee in os.path.basename(chemin) and cle in _cle_fichier(chemin)),
            None,
        )
        if not chemin_meta:
            continue
        try:
            codes = pd.read_csv(chemin_meta, sep=";", dtype=str, encoding="utf-8-sig", usecols=["COD_VAR"])["COD_VAR"]
        except (OSError, ValueError, UnicodeError, pd.errors.ParserError):
            continue
        codes = [code.strip() for code in codes.dropna().drop_duplicates() if code.strip()]
        prefixe_dico = theme.split(" ")[0]
        dict_vars = load_mapping(os.path.join(dossier_dicos, f"dictionnaire_variables_{prefixe_dico}.yml")) \
            if os.path.exists(os.path.join(dossier_dicos, f"dictionnaire_variables_{prefixe_dico}.yml")) else {}
        libelles_meta, _ = _charger_metadonnees(chemin_meta, codes)
        noms = preparer_colonnes_thematiques(
            pd.DataFrame(columns=codes), prefixe_dico, dict_vars, libelles_meta, dictionnaire_generique, {}
        ).columns
        vocabulaire[theme] = [
            str(nom) for code, nom in zip(codes, noms)
            if code.upper() not in {"IRIS", "COM", "TYP_IRIS", "LAB_IRIS", "CODGEO"}
        ]
    return vocabulaire


def ingerer_donnees_thematiques(
    dossier_data: str,
    dossier_dicos: str,
    chemin_modele: str | None = None,
    chemin_calculs: str | None = None,
    decisions_colonnes: list | None = None,
    dossier_reference: str | None = None,
) -> dict:
    """
    Fonction principale d'ingestion. Lit tous les CSV et Parquet du dossier, 
    filtre sur Roubaix, nettoie et renomme les variables.
    Retourne un dictionnaire { 'POP 2022': DataFrame, ... }
    Avec le modèle et/ou calculated_columns.yml, les colonnes inconnues sont rattachées
    ou nommées par modules/colonnes_auto.py ; les décisions sont ajoutées à decisions_colonnes.
    Seuls les millésimes plus récents que ceux de millesimes_valides.yml sont concernés : au premier
    lancement, ce fichier est créé avec le lot fourni, qui reste donc traité comme avant.
    dossier_reference : vrai dossier dictionnaires/ du dépôt (le portail travaille sur une copie
    sans méta) ; on y lit millesimes_valides.yml, le vocabulaire validé, et on y écrit le cache.
    """
    dossier_reference = dossier_reference or dossier_dicos
    dico_dataframes = {}
    references = charger_references(chemin_modele, chemin_calculs) if (chemin_modele or chemin_calculs) else None
    cache_colonnes = charger_cache(dossier_reference) if references is not None else {}
    cache_modifie = False
    millesimes_valides = charger_millesimes_valides(dossier_reference) if references is not None else {}
    premier_lancement = millesimes_valides is None
    if premier_lancement:
        millesimes_valides = {}
    vocabulaire_charge = False
    
    # Récupération du mapping des noms (ex: 'base-ic-evol-struct-pop' -> 'POP')
    mapping_noms = load_mapping(os.path.join(dossier_dicos, "files_names.yml"))
    
    for fichier in os.listdir(dossier_data):
        if not est_fichier_donnees(fichier):
            continue

        nom_base = os.path.splitext(fichier)[0]
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
        df_brut = lire_table(
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
        chemin_meta = trouver_fichier_meta(
            fichier,
            [os.path.join(dossier_dicos, "meta"), dossier_data, dossier_dicos],
        )
        libelles_metadonnees, modalites_metadonnees = _charger_metadonnees(
            chemin_meta,
            df_propre.columns.tolist(),
        )
        # preparer_colonnes_thematiques renomme df_propre sur place : codes source gardés avant
        codes_source = df_propre.columns.tolist()
        df_final = preparer_colonnes_thematiques(
            df_propre,
            prefixe_dico,
            dict_vars,
            libelles_metadonnees,
            dictionnaire_generique,
            modalites_metadonnees,
        )
        if premier_lancement:
            millesimes_valides[theme_identifie] = annee
        elif references is not None and millesime_a_traiter(theme_identifie, annee, millesimes_valides):
            if not vocabulaire_charge:
                # Lu une seule fois, et seulement si un fichier plus récent que le validé est présent
                for theme, noms in _vocabulaire_valide(dossier_reference, millesimes_valides, mapping_noms).items():
                    liste = references.setdefault(theme, [])
                    liste.extend(nom for nom in noms if nom not in liste)
                vocabulaire_charge = True
            df_final, decisions, modifie = resoudre_colonnes(
                df_final,
                cle_finale,
                codes_source,
                libelles_metadonnees,
                references,
                cache_colonnes,
            )
            cache_modifie = cache_modifie or modifie
            if decisions_colonnes is not None:
                decisions_colonnes.extend(decisions)
        dico_dataframes[cle_finale] = df_final

    if cache_modifie:
        enregistrer_cache(dossier_reference, cache_colonnes)
    if premier_lancement and references is not None and millesimes_valides:
        enregistrer_millesimes_valides(dossier_reference, millesimes_valides)
        print("Colonnes auto : millésimes actuels enregistrés comme validés (dictionnaires/millesimes_valides.yml).")
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


def lire_individus_recensement(
    chemin_fichier: str,
    taille_bloc: int = 250_000,
    chemin_meta: str | None = None,
):
    """Lit les variables enfants par blocs avec une estimation de progression."""
    if not os.path.exists(chemin_fichier):
        raise FileNotFoundError(f"Fichier de recensement introuvable : {chemin_fichier}")

    colonnes = ["IRIS", "AGEREV", "AGED", "IPONDI"]
    if chemin_meta:
        libelles_meta, _ = _charger_metadonnees(chemin_meta, colonnes)
        codes_documentes = set(libelles_meta)
        colonnes_sans_meta = [
            colonne for colonne in colonnes
            if _normaliser_identifiant(colonne) not in codes_documentes
        ]
        if colonnes_sans_meta:
            raise ValueError(
                "La métadonnée du recensement ne documente pas les colonnes requises : "
                + ", ".join(colonnes_sans_meta)
            )
    types = {
        "IRIS": str,
        "AGEREV": "float64",
        "AGED": "float64",
        "IPONDI": "float64",
    }
    # Parquet : nombre exact lu dans ses métadonnées ; CSV : estimation
    total_estime = compter_lignes(chemin_fichier) if est_parquet(chemin_fichier) else _estimer_nombre_lignes_csv(chemin_fichier)
    lecteur = lire_par_blocs(
        chemin_fichier,
        taille_bloc,
        sep=";",
        usecols=colonnes,
        dtype=types,
    )

    with tqdm(
        total=total_estime,
        desc="Lecture recensement enfants" + ("" if est_parquet(chemin_fichier) else " (lignes estimées)"),
        unit="lignes",
        unit_scale=True,
        dynamic_ncols=True,
    ) as barre:
        for bloc in lecteur:
            barre.update(len(bloc))
            yield bloc