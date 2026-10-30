# Liste des fichiers INSEE à fournir à l'application / mettre à jour

| Base | Nom du fichier | Description | Année de la dernière donnée | Lien de la page INSEE | Lien de téléchargement direct |
|-----------------------------------|-------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------|---------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| Activité des résidents | base-ic-activite-residents-2023.CSV | La base infracommunale « Activité des résidents » fournit des données sur les caractéristiques des actifs (sexe, âge, catégorie socio-professionnelle), des salariés et non-salariés (sexe et âge). | 2023 | https://www.insee.fr/fr/statistiques/9040859?sommaire=9040875#consulter | https://www.insee.fr/fr/statistiques/fichier/9040859/base-ic-activite-residents-2023_csv.zip |
| Couples - Familles - Ménages | base-ic-couples-familles-menages-2023.CSV | La base infracommunale « Couples - Familles - Ménages » fournit des données sur les caractéristiques des ménages, des personnes qui les composent (âge, statut conjugal, catégorie socio-professionnelle) et les caractéristiques des familles (nombre d'enfants). | 2023 | https://www.insee.fr/fr/statistiques/9058978?sommaire=9058987 | https://www.insee.fr/fr/statistiques/fichier/9058978/base-ic-couples-familles-menages-2023_csv.zip |
| Diplômes - Formation | base-ic-diplomes-formation-2023.CSV | La base infracommunale « Diplôme - Formation » fournit des données sur l'âge des personnes scolarisées et les niveaux de diplôme des personnes non scolarisées. | 2023 | https://www.insee.fr/fr/statistiques/9054820?sommaire=9054862#consulter | https://www.insee.fr/fr/statistiques/fichier/9054820/base-ic-diplomes-formation-2023_csv.zip |
| Population | base-ic-evol-struct-pop-2023.CSV | La base infracommunale « Population » fournit des données sur les caractéristiques de la population selon le sexe, l'âge, la catégorie socio-professionnelle et la catégorie de nationalité. | 2023 | https://www.insee.fr/fr/statistiques/9054332?sommaire=9054352#consulter | https://www.insee.fr/fr/statistiques/fichier/9054332/base-ic-evol-struct-pop-2023_csv.zip |
| Logement | base-ic-logement-2023.CSV | La base infracommunale « Logement » fournit des données sur les caractéristiques des résidences principales, la date d'emménagement, la possession d'une voiture ainsi que le parc de logements, maisons et appartements. | 2023 | https://www.insee.fr/fr/statistiques/9061333?sommaire=9061358#consulter | https://www.insee.fr/fr/statistiques/fichier/9061333/base-ic-logement-2023_csv.zip |
| Individus localisés au canton ou ville | FD_INDCVI_2023.csv | Fichier détail des individus (microdonnées). Permet d'extraire la distribution par âge révolu des enfants par IRIS, après filtrage sur Roubaix avec `scripts/extraire_indcvi_roubaix.py`. | 2023 | https://www.insee.fr/fr/statistiques/9075625?sommaire=9004842#consulter-sommaire | https://www.insee.fr/fr/statistiques/fichier/9075625/RP2023_indcvi.zip |
| CAF | data_CAF2024_Iris.csv | Cette base fournit des indicateurs sur les bénéficiaires des prestations légales versées par les CAF dans les quartiers politique de la ville. | 2024 | https://www.insee.fr/fr/statistiques/8682393 | https://www.insee.fr/fr/statistiques/fichier/8682393/beneficiaires_CAF_31-12-2024_Iris.zip |
| CNAM | data_CNAM2025_IRIS.csv | Cette base fournit des indicateurs sur les bénéficiaires du régime général de l'assurance maladie ainsi que sur les bénéficiaires de la Complémentaire Santé Solidaire (C2S) dans les quartiers prioritaires de la politique de la ville. | 2025 | https://www.insee.fr/fr/statistiques/8736938 | https://www.insee.fr/fr/statistiques/fichier/8736938/beneficiaires_CNAM_01-01-2025_Iris_csv.zip |
| Demandeurs d'emploi | data_DEFM2024_Iris.csv | Cette base fournit des indicateurs sur les demandeurs d'emploi en fin de mois au 31 décembre dans les quartiers prioritaires de la politique de la ville. | 2024 | https://www.insee.fr/fr/statistiques/8644875 | https://www.insee.fr/fr/statistiques/fichier/8644875/DEFM2024_Iris_csv.zip |
| Répertoire du Parc Locatif Social | data_RPLS2025_Iris.csv | Cette base fournit des indicateurs sur le parc des logements locatifs des bailleurs sociaux dans les quartiers prioritaires de la politique de la ville. | 2025 | https://www.insee.fr/fr/statistiques/9057420 | https://www.insee.fr/fr/statistiques/fichier/9057420/RPLS_01-01-2025_Iris.zip |

## Fichiers complémentaires du recensement (cubes `DS_RP_…_IRIS_AAAA`)

À déposer sous leur nom Insee dans `data/dataAAAA/complementaires/` (Parquet ou CSV). Le transformer en tire les colonnes du modèle que les 5 cubes principaux n'ont pas.

| Fichier | Apporte |
|---|---|
| DS_RP_POPULATION_COMP_IRIS_AAAA | Pop 15 ans ou plus par sexe et CSP (POP) |
| DS_RP_EMPLOI_LR_COMP_IRIS_AAAA | Actifs et actifs occupés 15-64 ans par CSP (ACT RES) |
| DS_RP_ACTIVITE_PRINC_IRIS_AAAA | Actifs occupés 15 ans ou plus, salariés, non-salariés, temps partiel, CDI / fonction publique (ACT RES) |
| DS_RP_NAVETTES_PRINC_IRIS_AAAA | Lieu de travail et mode de transport (ACT RES) |
| DS_RP_MENAGES_COMP_IRIS_AAAA | Ménages et population des ménages par type et CSP de la personne de référence (COU FAM) |
| DS_RP_FAMILLE_COMP_IRIS_AAAA | Familles par type et nombre d'enfants (COU FAM) |
| DS_RP_EDUCATION_PRINC_IRIS_AAAA | Population et population scolarisée par âge (DIP FORMATION) |
| DS_RP_LOGEMENT_COMP_IRIS_AAAA | Occupation des résidences principales : norme, sous- et suroccupation (LOG) |

# Comment les obtenir ?

Les fichiers meta contiennent le dictionnaire des variables. **Il faut les garder** : le portail exige un `meta_<nom du fichier>.csv` par fichier de données (zone **Métadonnées**), il en tire les libellés des colonnes. Les lots de `exemples/` montrent les noms attendus.

## Fichiers Population, Activité des résidents, Couples - Familles - Ménages, Diplômes - Formation et Logement

- Aller sur la page **Accès à l'ensemble des résultats statistiques de 2006 à 20XX** : https://www.insee.fr/fr/information/2880845
- Sélectionner les **résultats statistiques** de l'année la plus récente.
- Utiliser les liens des **Bases infracommunales**.

- Pour chaque lien télécharger le fichier **IRIS - France hors Mayotte** **au format CSV**.
- Depuis 2023, ces bases sont publiées en cubes au format long : les convertir avec `scripts/transformer_recensement.py` (voir `doc/nouveau_millesime.md`).

## Fichier Individus localisés au canton ou ville (Microdonnées)

- Aller sur la page **Fichiers détail du recensement de la population** : https://www.insee.fr/fr/statistiques/9075625?sommaire=9004842#consulter-sommaire
- Télécharger l'archive ZIP des **Individus localisés au canton-ou-ville (INDCVI)**.
- Extraire le fichier brut (`FD_INDCVI_2023.csv`, plusieurs Go) puis garder seulement Roubaix :

  ```
  python scripts/extraire_indcvi_roubaix.py "chemin\vers\FD_INDCVI_2023.csv"
  ```

- Déposer dans le portail la sortie `data/indcvi_roubaix/FD_INDCVI_2023.csv` (quelques Mo) avec la méta `varmod_indcvi_2023.csv`.

## Fichiers Demandeurs d'emploi, CAF, CNAM, Répertoire du logement social

- Aller sur la page **Données sur les quartiers de la politique de la ville (QPV)** : https://www.insee.fr/fr/statistiques/2500477
- Les données à utiliser sont alors les **données par source**, cliquer sur l'année la plus récente.

- Pour chaque thème, télécharger le fichier **au format CSV**.

Pour savoir quels fichiers garder, regarder le nom des fichiers dans le tableau plus haut. Les revenus Filosofi (REV DEC, REV DISP) ne sont plus dans le classeur : inutile de les télécharger.

## Base permanente des équipements

- Il n'y a malheureusement aucune page recensant les BPE par année.
- Une recherche Google permet néanmoins de retrouver facilement la page la plus récente : https://www.google.com/search?q=bpe+insee+iris
- Cliquer sur **Ensemble des thèmes** puis télécharger l'**Ensemble des bases au niveau IRIS**, en CSV ou en Parquet (plus léger), avec le fichier de métadonnées varmod (`BPE<AA>_anonymisee_varmod.csv`).
- Déposer le fichier national tel quel dans la page **Équipements BPE** du portail (voir le README) : le filtrage sur Roubaix ou la MEL est fait par l'application.