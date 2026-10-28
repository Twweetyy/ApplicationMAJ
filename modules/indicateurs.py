import pandas as pd
import numpy as np
import yaml
import os
import re
from .colonnes_auto import regle_colonne


COLONNES_IDENTIFIANTS_TEXTE = {
    "iris", "com", "com 1", "codgeo", "typ_iris", "lab_iris", "libiris", "note",
    "code géographique", "code geographique", "commune ou arm", "type d'iris",
    "label de l'iris", "libellé de l'iris",
}


def _precision_arrondi(nom_colonne: str, nom_table: str = ""):
    """Retourne la règle pour un champ: texte (None), ou nombre de décimales."""
    nom = nom_colonne.strip().casefold()
    code = re.sub(r"[^A-Z0-9]", "", nom_colonne.upper())

    if nom in COLONNES_IDENTIFIANTS_TEXTE:
        return None

    # Colonne créée par modules/colonnes_auto.py : précision donnée par le module
    regle = regle_colonne(nom_colonne, nom_table)
    if regle and regle.get("precision") is not None:
        return regle["precision"]

    rpls = "rpls" in nom_table.casefold()
    if rpls and (code.startswith("TX") or code.endswith("LOY")):
        return 2
    if rpls and ("loyer" in nom or nom.startswith(("taux", "part "))):
        return 2

    if (
        "(%)" in nom
        or nom.startswith(("part", "taux"))
        or "pourcentage" in nom
    ):
        return 1

    # Indicateurs de dispersion des revenus (Filosofi) : précision de l'Insee
    if nom.startswith("indice de gini"):
        return 3
    if nom.startswith(("écart inter", "ecart inter")):
        return 2
    if nom.startswith(("rapport interdécile", "rapport interdecile", "s80/s20")):
        return 1

    if nom.startswith(("densité", "densite", "indice", "taille", "superficie")):
        return 2

    return 0


def _arrondir_nombre_entier(valeurs: pd.Series) -> pd.Series:
    numeriques = pd.to_numeric(valeurs, errors="coerce")
    arrondies = np.sign(numeriques) * np.floor(np.abs(numeriques) + 0.5)
    return pd.Series(arrondies, index=valeurs.index).astype("Int64")


def _arrondi_controle(valeurs: pd.Series) -> pd.Series:
    """Arrondit à l'entier en conservant le total (méthode du plus fort reste).

    Les effectifs Insee à l'IRIS ont des décimales : arrondis un par un, leur somme peut s'écarter
    de quelques unités du chiffre communal officiel (ex. 98 284 au lieu de 98 286 habitants).
    Ici on part de la partie entière de chaque IRIS et on ajoute 1 aux IRIS qui ont les plus
    grandes décimales, jusqu'à atteindre l'arrondi de la somme exacte.
    """
    numeriques = pd.to_numeric(valeurs, errors="coerce")
    presentes = numeriques.dropna()
    if presentes.empty or (presentes < 0).any() or (presentes == np.floor(presentes)).all():
        return _arrondir_nombre_entier(valeurs)
    entiers = np.floor(presentes)
    a_repartir = int(np.floor(presentes.sum() + 0.5) - entiers.sum())
    plus_forts_restes = (presentes - entiers).sort_values(ascending=False, kind="stable").index[:a_repartir]
    entiers.loc[plus_forts_restes] += 1
    return entiers.reindex(numeriques.index).astype("Int64")


def _convertir_identifiant_en_texte(valeur):
    if pd.isna(valeur):
        return pd.NA
    if isinstance(valeur, (int, np.integer)):
        return str(valeur)
    if isinstance(valeur, (float, np.floating)) and valeur.is_integer():
        return str(int(valeur))
    return str(valeur)


def arrondir_variables(fichiers: dict) -> dict:
    """Applique automatiquement les règles d'arrondi à toutes les colonnes numériques.

    Les effectifs additifs (ceux qui ont un total dans le classeur) sont arrondis par
    _arrondi_controle, pour que le total affiché égale le chiffre communal officiel.
    """
    from .mise_en_page import _est_additive  # import local : mise_en_page importe ce module

    for nom_table, dataframe in fichiers.items():
        resultat = dataframe.copy()
        for colonne in resultat.columns:
            precision = _precision_arrondi(str(colonne), nom_table)
            if precision is None:
                if str(colonne).strip().casefold() in {
                    "com", "com 1", "codgeo", "code géographique", "code geographique",
                    "typ_iris", "lab_iris", "libiris", "iris",
                }:
                    resultat[colonne] = resultat[colonne].map(_convertir_identifiant_en_texte).astype("string")
                else:
                    resultat[colonne] = resultat[colonne].astype("string")
                continue
            if not pd.api.types.is_numeric_dtype(resultat[colonne]):
                valeurs_texte = resultat[colonne].astype("string").str.strip().str.replace(",", ".", regex=False)
                non_vides = valeurs_texte.notna() & valeurs_texte.ne("")
                numeriques = pd.to_numeric(valeurs_texte, errors="coerce")
                if not non_vides.any() or not numeriques.loc[non_vides].notna().all():
                    continue
                resultat[colonne] = numeriques
            if precision == 0 and _est_additive(str(colonne), nom_table, 0):
                resultat[colonne] = _arrondi_controle(resultat[colonne])
            elif precision == 0:
                resultat[colonne] = _arrondir_nombre_entier(resultat[colonne])
            else:
                resultat[colonne] = pd.to_numeric(resultat[colonne], errors="coerce").round(precision)
        fichiers[nom_table] = resultat
    return fichiers


def arrondir_effectifs(fichiers: dict) -> dict:
    """Alias conservé pour les appels historiques; applique toutes les règles d'arrondi."""
    return arrondir_variables(fichiers)


def _resoudre_table(nom, fichiers: dict):
    """Retrouve la table d'un thème quel que soit le millésime (ex. 'POP 2022' -> 'POP 2023')."""
    if not isinstance(nom, str) or nom in fichiers:
        return nom
    theme = nom.rsplit(" ", 1)[0]
    correspondances = [
        nom_fichier
        for nom_fichier in fichiers
        if isinstance(nom_fichier, str) and nom_fichier.rsplit(" ", 1)[0] == theme
    ]
    return correspondances[0] if len(correspondances) == 1 else nom

def ajouter_indicateurs_calcules(fichiers: dict, chemin_yaml: str) -> dict:
    """
    Calcule de nouvelles colonnes (taux, parts, évolutions) à partir d'expressions
    mathématiques stockées dans un fichier YAML.
    """
    if not os.path.exists(chemin_yaml):
        print(f"Attention : Fichier de calculs introuvable -> {chemin_yaml}")
        return fichiers

    with open(chemin_yaml, "r", encoding="UTF-8") as file:
        yaml_calculs = yaml.safe_load(file)

    if not yaml_calculs:
        return fichiers

    for indicateur_nom, params in yaml_calculs.items():
        expression = params.get("expression")
        df_name = params.get("df")
        var1 = params.get("var1")
        var2 = params.get("var2")
        var3 = params.get("var3")
        var4 = params.get("var4")
        
        df_name = _resoudre_table(df_name, fichiers)
        if df_name not in fichiers:
            continue
        expression = re.sub(
            r"""files\[\s*["']([^"']+)["']\s*\]""",
            lambda m: f'files["{_resoudre_table(m.group(1), fichiers)}"]',
            expression,
        )
            
        df = fichiers[df_name]
        
        # Sécurité anti-doublons de colonnes avant le calcul
        df = df.loc[:, ~df.columns.duplicated()].reset_index(drop=True)
        
        try:
            # Exécution dynamique de la formule
            valeurs_calculees = pd.eval(
                expression, 
                engine='python', 
                parser='pandas', 
                local_dict={
                    'files': fichiers, 
                    'df': df_name, 
                    'var1': var1, 
                    'var2': var2, 
                    'var3': var3,
                    'var4': var4,
                    'np': np
                }
            )
            precision = _precision_arrondi(indicateur_nom, df_name)
            if precision is None or precision == 0:
                df[indicateur_nom] = valeurs_calculees.replace([np.inf, -np.inf], np.nan)
            else:
                df[indicateur_nom] = valeurs_calculees.round(precision).replace([np.inf, -np.inf], np.nan)
            
        except ZeroDivisionError:
            # Gestion des divisions par zéro (ex: population de référence = 0)
            df[indicateur_nom] = 100 * df[var1].div(df[var2].replace(0, np.nan))
            
        except KeyError as e:
            # Variable absente des fichiers du lot (ex. « Pop 60-74 ans », absente du recensement 2023)
            print(f"Indicateur non calculé '{indicateur_nom}' : variable absente de ce millésime ({e.args[0]})")

        except Exception as e:
            print(f"Erreur lors du calcul de '{indicateur_nom}' : {e}")
            
        fichiers[df_name] = df

    return fichiers


def calculer_repartition_enfants(blocs_individus) -> dict:
    """Calcule les répartitions d'enfants par IRIS en pondérant par IPONDI."""
    specifications = {
        "Enfants âge révolu": "AGEREV",
        "Enfants âge millésime": "AGED",
    }
    groupes = {nom: [] for nom in specifications}

    for bloc in blocs_individus:
        bloc = bloc.loc[bloc["IRIS"].astype(str).str.startswith("59512", na=False)]
        for nom_table, colonne_age in specifications.items():
            enfants = bloc.loc[bloc[colonne_age].lt(18), ["IRIS", colonne_age, "IPONDI"]]
            enfants = enfants.dropna(subset=["IRIS", colonne_age])
            groupe = enfants.groupby(["IRIS", colonne_age], as_index=False)["IPONDI"].sum()
            groupes[nom_table].append(groupe)

    resultats = {}
    for nom_table, colonne_age in specifications.items():
        if groupes[nom_table]:
            agrege = pd.concat(groupes[nom_table], ignore_index=True)
            agrege = agrege.groupby(["IRIS", colonne_age], as_index=False)["IPONDI"].sum()
            tableau = agrege.pivot(index="IRIS", columns=colonne_age, values="IPONDI")
            tableau = tableau.reindex(columns=range(18), fill_value=0).fillna(0)
            tableau.columns = [f"Age : {age}" for age in tableau.columns]
            tableau = tableau.reset_index()
        else:
            tableau = pd.DataFrame(columns=["IRIS", *[f"Age : {age}" for age in range(18)]])
        resultats[nom_table] = tableau

    return resultats