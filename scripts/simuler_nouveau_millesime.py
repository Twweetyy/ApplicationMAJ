"""Faux millésime pour tester le module colonnes_auto (IA comprise) sans toucher au vrai dépôt.

Copie un lot validé dans un dossier temporaire, avance d'un an les fichiers du recensement
(base-ic-*), renomme quelques codes et reformule leur libellé méta, en retire un, puis lance le pipeline
avec une copie de dictionnaires/. Le vrai cache correspondances_auto.yml n'est pas modifié.

    python scripts/simuler_nouveau_millesime.py --lot data/data2023
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile

import pandas as pd

DOSSIER_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DOSSIER_RACINE)

from main_bddmas import FICHIER_MODELE, executer_pipeline  # noqa: E402
from modules.ingestion import trouver_fichier_meta  # noqa: E402

DOSSIER_DICOS = os.path.join(DOSSIER_RACINE, "dictionnaires")
DOSSIER_SORTIE = os.path.join(DOSSIER_RACINE, "sorties", "simulation")


def _annee_suivante(nom: str) -> str:
    return re.sub(r"(?<!\d)(20\d{2})(?!\d)", lambda m: str(int(m.group(1)) + 1), nom, count=1)


def _code_suivant(code: str) -> str:
    """P23_POP -> P24_POP (préfixe millésime INSEE), sinon inchangé."""
    return re.sub(r"^([A-Z])(\d{2})_", lambda m: f"{m.group(1)}{int(m.group(2)) + 1:02d}_", str(code))


def _reformuler(libelle: str, rang: int) -> str:
    """Un libellé sur 4 reformulé simplement (attendu : rattaché sans IA), un sur 7 plus fortement (IA)."""
    if rang % 7 == 3:
        return f"Nombre de {libelle[0].lower()}{libelle[1:]}"
    if rang % 4 == 1:
        texte = re.sub(r"\bPop\b", "Population", libelle)
        return re.sub(r"(\d+)-(\d+) ans", r"de \1 à \2 ans", texte)
    return libelle


def preparer_lot(lot: str, dossier_tmp: str) -> tuple[str, str, list[str]]:
    lot_tmp = os.path.join(dossier_tmp, "lot")
    dicos_tmp = os.path.join(dossier_tmp, "dictionnaires")
    os.makedirs(lot_tmp)
    # Cubes INSEE bruts inutiles ici (lourds, surtout sur le partage réseau)
    shutil.copytree(DOSSIER_DICOS, dicos_tmp, ignore=shutil.ignore_patterns("sources_brutes_meta"))
    cache_tmp = os.path.join(dicos_tmp, "correspondances_auto.yml")
    if os.path.isfile(cache_tmp):
        os.remove(cache_tmp)
    dossier_meta_sim = os.path.join(dicos_tmp, "meta", "meta_simulation")
    os.makedirs(dossier_meta_sim, exist_ok=True)

    retirees = []
    for fichier in sorted(os.listdir(lot)):
        source = os.path.join(lot, fichier)
        if not os.path.isfile(source) or fichier.casefold().startswith("meta_"):
            continue
        if not fichier.casefold().startswith("base-ic-"):
            try:
                # Lien plutôt que copie : FD_INDCVI pèse plusieurs Go
                os.link(source, os.path.join(lot_tmp, fichier))
            except OSError:
                shutil.copy2(source, os.path.join(lot_tmp, fichier))
            continue
        nouveau = _annee_suivante(fichier)
        # Codes renommés (suffixe X) : sinon dictionnaire_variables_*.yml retrouve le libellé
        # par le code et la reformulation de la méta ne se voit jamais
        renommes = {}
        chemin_meta = trouver_fichier_meta(fichier, [os.path.join(DOSSIER_DICOS, "meta"), lot])
        if chemin_meta:
            meta = pd.read_csv(chemin_meta, sep=";", dtype=str, encoding="utf-8-sig")
            colonnes_meta = {colonne.upper(): colonne for colonne in meta.columns}
            cod, lib = colonnes_meta["COD_VAR"], colonnes_meta["LIB_VAR"]
            meta[cod] = meta[cod].map(_code_suivant)
            variables = [code for code in meta[cod].dropna().unique() if code.upper() not in {"COM", "IRIS", "TYP_IRIS", "LAB_IRIS", "CODGEO"}]
            for rang, code in enumerate(variables):
                masque = meta[cod] == code
                nouveau_libelle = _reformuler(str(meta.loc[masque, lib].iloc[0]), rang)
                if nouveau_libelle != meta.loc[masque, lib].iloc[0]:
                    renommes[code] = f"{code}X"
                    meta.loc[masque, lib] = nouveau_libelle
            # Une variable sans méta : l'IA ne voit que son code et ses valeurs
            if len(variables) > 5:
                retiree = variables[len(variables) // 2]
                meta = meta[meta[cod] != retiree]
                renommes[retiree] = f"{retiree}X"
                retirees.append(f"{nouveau} : {retiree}X")
            meta[cod] = meta[cod].map(lambda code: renommes.get(code, code))
            nom_meta = "meta_" + os.path.splitext(nouveau)[0] + ".csv"
            meta.to_csv(os.path.join(dossier_meta_sim, nom_meta), sep=";", index=False, encoding="utf-8")
        else:
            print(f"Pas de méta pour {fichier} : copié sans reformulation.")

        with open(source, "r", encoding="utf-8-sig", newline="") as entree:
            entete = entree.readline()
            reste = entree.read()
        separateur = ";" if ";" in entete else ","
        fin = "\r\n" if entete.endswith("\r\n") else "\n"
        colonnes = [_code_suivant(colonne) for colonne in entete.rstrip("\r\n").split(separateur)]
        colonnes = [renommes.get(colonne, colonne) for colonne in colonnes]
        with open(os.path.join(lot_tmp, nouveau), "w", encoding="utf-8", newline="") as sortie:
            sortie.write(separateur.join(colonnes) + fin + reste)
        print(f"{nouveau} : {len(renommes)} code(s) renommé(s)")
    return lot_tmp, dicos_tmp, retirees


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lot", required=True, help="dossier du lot validé (fichiers à plat, comme déposés dans le portail)")
    parser.add_argument("--garder", action="store_true", help="garder le dossier temporaire pour inspection")
    arguments = parser.parse_args()

    os.makedirs(DOSSIER_SORTIE, exist_ok=True)
    dossier_tmp = tempfile.mkdtemp(prefix="bddmas_simulation_")
    try:
        lot_tmp, dicos_tmp, retirees = preparer_lot(os.path.abspath(arguments.lot), dossier_tmp)
        print("Fichiers simulés :", ", ".join(sorted(os.listdir(lot_tmp))))
        print("Variables sans méta (pour l'IA) :", ", ".join(retirees) or "aucune")
        classeur = os.path.join(DOSSIER_SORTIE, "TAB_BDDMAS_simulation.xlsx")
        resultat = executer_pipeline(
            lot_tmp,
            dicos_tmp,
            classeur,
            chemin_modele=FICHIER_MODELE,
            afficher_progression=True,
            afficher_messages=True,
        )
        decisions = resultat.get("colonnes_auto", [])
        with open(os.path.join(DOSSIER_SORTIE, "decisions.json"), "w", encoding="utf-8") as fichier:
            json.dump(decisions, fichier, ensure_ascii=False, indent=2, default=str)
        cache = os.path.join(dicos_tmp, "correspondances_auto.yml")
        if os.path.isfile(cache):
            shutil.copy2(cache, os.path.join(DOSSIER_SORTIE, "correspondances_auto_simulation.yml"))
        compte = {}
        for decision in decisions:
            cle = f"{decision['methode']} / {decision['decision']}"
            compte[cle] = compte.get(cle, 0) + 1
        print("\nDécisions :", json.dumps(compte, ensure_ascii=False))
        print(f"Résultats dans {DOSSIER_SORTIE} (classeur, decisions.json, correspondances_auto_simulation.yml)")
    finally:
        if arguments.garder:
            print(f"Dossier temporaire conservé : {dossier_tmp}")
        else:
            shutil.rmtree(dossier_tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
