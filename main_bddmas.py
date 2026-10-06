import os
from time import perf_counter
from tqdm.auto import tqdm
from modules.socle_geo import ajouter_superficies_iris, charger_referentiel_mas, joindre_perimetre
from modules.ingestion import ingerer_donnees_thematiques, lire_individus_recensement, trouver_fichier_meta
from modules.indicateurs import ajouter_indicateurs_calcules, arrondir_variables
from modules.indicateurs import calculer_repartition_enfants
from modules.export_excel import generer_fichier_bddmas
from modules.export_sig import exporter_tables_sig
from modules.persistence import persister_dans_bddmas

DOSSIER_COURANT = os.path.dirname(os.path.abspath(__file__))
DOSSIER_DATA = os.path.join(DOSSIER_COURANT, "data")
DOSSIER_DICOS = os.path.join(DOSSIER_COURANT, "dictionnaires")

FICHIER_PERIMETRE = os.path.join(DOSSIER_DATA, "Périmètres_MAS.csv")
FICHIER_SUPERFICIES = os.path.join(DOSSIER_DICOS, "superficies_iris_roubaix.yml")
FICHIER_INDIVIDUS = os.path.join(DOSSIER_DATA, "FD_INDCVI_2022.csv")
FICHIER_MODELE = os.path.join(DOSSIER_COURANT, "TAB_BDDMAS_INSEE2022_MODELE.xlsx")
DOSSIER_EXPORT_SIG = os.path.join(DOSSIER_COURANT, "exports_sig")
FICHIER_CALCULS = os.path.join(DOSSIER_DICOS, "calculated_columns.yml")
FICHIER_INFOS = os.path.join(DOSSIER_DICOS, "info_pages.yml")
FICHIER_SORTIE = os.path.join(DOSSIER_COURANT, "TAB_BDDMAS_INSEE2022_Tout_perimetre.xlsx")

def main():
    debut = perf_counter()
    print("=== PIPELINE BDDMAS ROUBAIX ===")

    with tqdm(total=9, desc="Pipeline BDDMAS", unit="étapes", dynamic_ncols=True) as progression:
        progression.set_postfix_str("ingestion des thèmes")
        dico_fichiers = ingerer_donnees_thematiques(DOSSIER_DATA, DOSSIER_DICOS)
        progression.update(1)

        progression.set_postfix_str("calcul des enfants pondérés")
        if os.path.exists(FICHIER_INDIVIDUS):
            meta_individus = trouver_fichier_meta(
                FICHIER_INDIVIDUS,
                [os.path.join(DOSSIER_DICOS, "meta")],
            )
            blocs_individus = lire_individus_recensement(
                FICHIER_INDIVIDUS,
                chemin_meta=meta_individus,
            )
            repartitions = calculer_repartition_enfants(blocs_individus)
            dico_fichiers["PETITE ENFANCE 2022"] = repartitions["Enfants âge révolu"]
            dico_fichiers["PETITE ENFANCE MILLÉSIME"] = repartitions["Enfants âge millésime"]
        else:
            print(f"Traitement enfants ignoré, fichier absent : {FICHIER_INDIVIDUS}")
        progression.update(1)

        progression.set_postfix_str("référentiel géographique")
        df_perimetre = charger_referentiel_mas(FICHIER_PERIMETRE)
        dico_fichiers = joindre_perimetre(dico_fichiers, df_perimetre)
        dico_fichiers = ajouter_superficies_iris(dico_fichiers, FICHIER_SUPERFICIES)
        progression.update(1)

        progression.set_postfix_str("préparation du modèle")
        from modules.export_excel import creer_modele_si_absent
        creer_modele_si_absent(dico_fichiers, FICHIER_MODELE, FICHIER_INFOS)
        progression.update(1)

        progression.set_postfix_str("calcul des indicateurs")
        dico_fichiers = ajouter_indicateurs_calcules(dico_fichiers, FICHIER_CALCULS)
        progression.update(1)

        progression.set_postfix_str("arrondi des effectifs")
        dico_fichiers = arrondir_variables(dico_fichiers)
        progression.update(1)

        progression.set_postfix_str("export du classeur")
        generer_fichier_bddmas(dico_fichiers, FICHIER_SORTIE, FICHIER_INFOS, FICHIER_MODELE)
        progression.update(1)

        progression.set_postfix_str("exports SIG")
        exporter_tables_sig(dico_fichiers, DOSSIER_EXPORT_SIG)
        progression.update(1)

        progression.set_postfix_str("persistance SQL (optionnelle)")
        persister_dans_bddmas(dico_fichiers)
        progression.update(1)
        progression.set_postfix_str(f"terminé en {perf_counter() - debut:.1f} s")

if __name__ == "__main__":
    main()