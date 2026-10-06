import os
from contextlib import nullcontext
from time import perf_counter
from tqdm.auto import tqdm
from modules.socle_geo import ajouter_superficies_iris, charger_referentiel_mas, joindre_perimetre
from modules.ingestion import (
    analyser_fichiers_entree,
    ingerer_donnees_thematiques,
    lire_individus_recensement,
    trouver_fichier_meta,
)
from modules.indicateurs import ajouter_indicateurs_calcules, arrondir_variables
from modules.indicateurs import calculer_repartition_enfants
from modules.export_excel import generer_fichier_bddmas
from modules.export_sig import exporter_tables_sig
from modules.persistence import persister_dans_bddmas

DOSSIER_COURANT = os.path.dirname(os.path.abspath(__file__))
DOSSIER_DATA = os.path.join(DOSSIER_COURANT, "data")
DOSSIER_DICOS = os.path.join(DOSSIER_COURANT, "dictionnaires")

FICHIER_SUPERFICIES = os.path.join(DOSSIER_DICOS, "superficies_iris_roubaix.yml")
FICHIER_MODELE = os.path.join(DOSSIER_COURANT, "TAB_BDDMAS_INSEE2022_MODELE.xlsx")
DOSSIER_EXPORT_SIG = os.path.join(DOSSIER_COURANT, "exports_sig")
FICHIER_CALCULS = os.path.join(DOSSIER_DICOS, "calculated_columns.yml")
FICHIER_INFOS = os.path.join(DOSSIER_DICOS, "info_pages.yml")
FICHIER_SORTIE = os.path.join(DOSSIER_COURANT, "TAB_BDDMAS_INSEE2022_Tout_perimetre.xlsx")

class ErreurPrecontrole(ValueError):
    def __init__(self, rapport: dict):
        self.rapport = rapport
        super().__init__("Pré-contrôle bloquant : le pipeline n'a pas été lancé.")


def executer_pipeline(
    dossier_data: str,
    dossier_dicos: str,
    chemin_sortie: str,
    chemin_modele: str | None = None,
    dossier_export_sig: str | None = None,
    chemin_superficies: str | None = None,
    chemin_calculs: str | None = None,
    chemin_infos_onglets: str | None = None,
    persister_sql: bool = False,
    afficher_progression: bool = False,
    afficher_messages: bool = False,
) -> dict:
    """Exécute un lot fourni par l'appelant et retourne les résultats du traitement."""
    debut = perf_counter()
    rapport_precontrole = analyser_fichiers_entree(dossier_data, dossier_dicos)
    nombre_themes = sum(source["role"] == "theme" for source in rapport_precontrole["sources"])
    if afficher_messages:
        print(
            "Pré-contrôle : "
            f"{nombre_themes} sources thématiques, "
            f"{sum(source['role'] == 'perimetre' for source in rapport_precontrole['sources'])} périmètre, "
            f"{sum(source['role'] == 'microdonnees_enfants' for source in rapport_precontrole['sources'])} fichier(s) enfants."
        )
        for avertissement in rapport_precontrole["avertissements"]:
            fichier = avertissement.get("fichier", "")
            print(f"AVERTISSEMENT {fichier} : {avertissement['message']}")
    if rapport_precontrole["erreurs"]:
        if afficher_messages:
            for erreur in rapport_precontrole["erreurs"]:
                fichier = erreur.get("fichier", "")
                print(f"ERREUR {fichier} : {erreur['message']}")
        raise ErreurPrecontrole(rapport_precontrole)

    source_perimetre = next(
        source for source in rapport_precontrole["sources"] if source["role"] == "perimetre"
    )
    chemin_perimetre = os.path.join(dossier_data, source_perimetre["fichier"])
    source_individus = next(
        (source for source in rapport_precontrole["sources"] if source["role"] == "microdonnees_enfants"),
        None,
    )
    chemin_individus = (
        os.path.join(dossier_data, source_individus["fichier"])
        if source_individus
        else None
    )
    chemin_superficies = chemin_superficies or os.path.join(dossier_dicos, "superficies_iris_roubaix.yml")
    chemin_calculs = chemin_calculs or os.path.join(dossier_dicos, "calculated_columns.yml")
    chemin_infos_onglets = chemin_infos_onglets or os.path.join(dossier_dicos, "info_pages.yml")

    nombre_etapes = 7 + int(dossier_export_sig is not None) + int(persister_sql)
    progression_context = (
        tqdm(total=nombre_etapes, desc="Pipeline BDDMAS", unit="étapes", dynamic_ncols=True)
        if afficher_progression
        else nullcontext(None)
    )
    exports_sig = []
    tables_sql = []

    with progression_context as progression:
        if progression is not None:
            progression.set_postfix_str("ingestion des thèmes")
        dico_fichiers = ingerer_donnees_thematiques(dossier_data, dossier_dicos)
        if progression is not None:
            progression.update(1)

        if progression is not None:
            progression.set_postfix_str("calcul des enfants pondérés")
        if chemin_individus:
            meta_individus = trouver_fichier_meta(chemin_individus, [os.path.join(dossier_dicos, "meta")])
            blocs_individus = lire_individus_recensement(
                chemin_individus,
                chemin_meta=meta_individus,
            )
            repartitions = calculer_repartition_enfants(blocs_individus)
            dico_fichiers["PETITE ENFANCE 2022"] = repartitions["Enfants âge révolu"]
            dico_fichiers["PETITE ENFANCE MILLÉSIME"] = repartitions["Enfants âge millésime"]
        if progression is not None:
            progression.update(1)

        if progression is not None:
            progression.set_postfix_str("référentiel géographique")
        df_perimetre = charger_referentiel_mas(chemin_perimetre)
        dico_fichiers = joindre_perimetre(dico_fichiers, df_perimetre)
        dico_fichiers = ajouter_superficies_iris(dico_fichiers, chemin_superficies)
        if progression is not None:
            progression.update(1)

        if progression is not None:
            progression.set_postfix_str("préparation du modèle")
        from modules.export_excel import creer_modele_si_absent
        creer_modele_si_absent(dico_fichiers, chemin_modele, chemin_infos_onglets)
        if progression is not None:
            progression.update(1)

        if progression is not None:
            progression.set_postfix_str("calcul des indicateurs")
        dico_fichiers = ajouter_indicateurs_calcules(dico_fichiers, chemin_calculs)
        if progression is not None:
            progression.update(1)

        if progression is not None:
            progression.set_postfix_str("arrondi des effectifs")
        dico_fichiers = arrondir_variables(dico_fichiers)
        if progression is not None:
            progression.update(1)

        if progression is not None:
            progression.set_postfix_str("export du classeur")
        generer_fichier_bddmas(dico_fichiers, chemin_sortie, chemin_infos_onglets, chemin_modele)
        if progression is not None:
            progression.update(1)

        if dossier_export_sig is not None:
            if progression is not None:
                progression.set_postfix_str("exports SIG")
            exports_sig = exporter_tables_sig(dico_fichiers, dossier_export_sig)
            if progression is not None:
                progression.update(1)

        if persister_sql:
            if progression is not None:
                progression.set_postfix_str("persistance SQL (optionnelle)")
            tables_sql = persister_dans_bddmas(dico_fichiers)
            if progression is not None:
                progression.update(1)

        if progression is not None:
            progression.set_postfix_str(f"terminé en {perf_counter() - debut:.1f} s")

    return {
        "precontrole": rapport_precontrole,
        "classeur": chemin_sortie,
        "exports_sig": [str(chemin) for chemin in exports_sig],
        "tables_sql": tables_sql,
        "themes": list(dico_fichiers),
        "duree_secondes": perf_counter() - debut,
    }


def main():
    print("=== PIPELINE BDDMAS ROUBAIX ===")
    return executer_pipeline(
        DOSSIER_DATA,
        DOSSIER_DICOS,
        FICHIER_SORTIE,
        chemin_modele=FICHIER_MODELE,
        dossier_export_sig=DOSSIER_EXPORT_SIG,
        chemin_superficies=FICHIER_SUPERFICIES,
        chemin_calculs=FICHIER_CALCULS,
        chemin_infos_onglets=FICHIER_INFOS,
        persister_sql=True,
        afficher_progression=True,
        afficher_messages=True,
    )

if __name__ == "__main__":
    main()