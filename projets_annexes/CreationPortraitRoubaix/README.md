# CreationPortraitRoubaix : portrait statistique des Comités de Quartier de Roubaix

## À quoi sert ce projet

Roubaix est découpée par l'Insee en **38 IRIS**, les plus petites zones pour lesquelles des statistiques sont publiées. Les acteurs de terrain, eux, raisonnent en **Comités de Quartier (CQ)**. Ce mini-projet fait le lien entre les deux : il regroupe les IRIS par CQ et produit, pour chaque CQ et pour la ville entière, un portrait chiffré prêt à lire.

À partir des données déjà rassemblées par IRIS (recensement, revenus, CAF, Assurance maladie, demandeurs d'emploi, logements sociaux, équipements), un seul script produit :

- un **classeur Excel** de présentation, qui s'ouvre sur une page d'accueil avec les chiffres clés de Roubaix et une page récap par CQ ;
- un **GeoJSON** des contours des CQ avec tous leurs indicateurs, pour faire des cartes (ArcGIS, QGIS…).

Le portrait couvre 108 indicateurs répartis en quatre thèmes (31 en démographie, 36 en socio-économie, 28 en logement et 13 en équipements) :

| Thème | Contenu |
|---|---|
| Démographie | Population, densité, évolution depuis 2006 et 2016, tranches d'âge, genre, taille et composition des ménages, familles monoparentales et nombreuses |
| Socio-économie | Revenus et pauvreté, activité, emploi, chômage, catégories socioprofessionnelles, diplômes, précarité (CAF, RSA, AAH, C2S, demandeurs d'emploi) |
| Logement | Parc, vacance, statut d'occupation, logements sociaux, taille, époque de construction, ancienneté d'emménagement, suroccupation |
| Équipements | Écoles, collèges, lycées, crèches, équipements culturels et sportifs, centres sociaux, services publics, bureaux de poste, commerces de proximité |

## Ce que contient le classeur produit

`data/traite/portrait_cq_<ANNEE>.xlsx` contient :

- **TOUT_ROUBAIX** (page d'accueil) : les chiffres clés de la ville, une colonne par thème, les sources avec leur millésime, les points à connaître, et des boutons vers chaque page récap ;
- **un onglet par thème** (Démographie, Socio-économie, Logement, Équipements) : une ligne par CQ et une ligne Roubaix, une colonne par indicateur, avec la source et l'année dans l'en-tête ;
- **Méthode** : pour chaque indicateur, sa source, son mode de calcul et les colonnes utilisées ;
- **Rattachement IRIS** : les 38 IRIS et le CQ auquel chacun appartient ;
- **RECAP_<CQ>** (une par CQ, par exemple `RECAP_Sainte_Elisabeth`) : les mêmes chiffres clés que l'accueil pour le CQ, son poids dans la population de Roubaix et un lien « Retour à TOUT_ROUBAIX ».

`data/traite/cq_roubaix_<ANNEE>.geojson` contient un polygone par CQ, obtenu en fusionnant ses IRIS, avec tous les indicateurs.

## Organisation du dossier

```
CreationPortraitRoubaix/
├─ README.md
├─ scripts/
│  ├─ portrait_cq.py        calcule les indicateurs et écrit le classeur et le GeoJSON
│  └─ accueil.py            dessine la page d'accueil et les pages récap (3 modèles au choix)
└─ data/
   ├─ brut/
   │  └─ BPE<AA>_Roubaix_equipements_officiel.xlsx   équipements (Insee), à remplacer à chaque millésime
   ├─ ref/
   │  ├─ cq_iris.yml           rattachement des IRIS aux CQ
   │  └─ roubaix_commune.yml   indicateurs publiés seulement pour la commune (Filosofi 2023)
   └─ traite/               sorties du script
```

## D'où viennent les données

Le projet s'appuie sur le projet voisin **CreationMASGeojson**, qui doit se trouver dans le même dossier parent. Il y lit :

| Fichier | Rôle | Produit par |
|---|---|---|
| `TAB_BDDMAS_Tout_perimetre_<ANNEE>.xlsx` | Toutes les données Insee, CAF, CNAM, France Travail et RPLS par IRIS | ApplicationMAJ |
| `Iris_2000.geojson` | Contours des 38 IRIS | fichier fixe |
| `stat_insee_iris_<ANNEE>.xlsx` | Populations historiques 2006 et 2016 | `etl_iris.py` de CreationMASGeojson |

Un fichier du même nom déposé dans `data/brut` ou `data/traite` de CreationPortraitRoubaix est pris en priorité.

Les équipements viennent de la **Base permanente des équipements (BPE)** de l'Insee, déposée dans `data/brut` (voir plus bas).

## Installation (une seule fois)

```
pip install pandas openpyxl pyyaml shapely
```

## Produire le portrait

1. Dans CreationMASGeojson, générer d'abord `stat_insee_iris_<ANNEE>.xlsx` :
   ```
   python scripts/etl_iris.py 2023
   ```
2. Vérifier que le fichier BPE est dans `data/brut` de CreationPortraitRoubaix.
3. Depuis le dossier CreationPortraitRoubaix, lancer :
   ```
   python scripts/portrait_cq.py 2023
   ```
   Sans argument, le script traite 2023. Les sorties sont écrites dans `data/traite`.

Pour un nouveau millésime (par exemple 2024), il suffit de régénérer le TAB 2024 avec ApplicationMAJ, de relancer `etl_iris.py 2024`, puis `portrait_cq.py 2024`.

## Comment les chiffres sont calculés

- **Comptages et parts :** les effectifs des IRIS du CQ sont additionnés, puis les parts et taux sont recalculés sur ces sommes. Ce ne sont jamais des moyennes de taux d'IRIS.
- **Revenus (taux de pauvreté, revenu médian, part des prestations) :** ils ne s'additionnent pas. Pour un CQ, ils sont donc « approchés » : moyenne des IRIS pondérée par la population des ménages (Filosofi 2021). Pour un CQ d'un seul IRIS, c'est la valeur exacte de l'Insee. Un IRIS secrétisé est exclu du calcul, et la case reste vide si tous les IRIS du CQ le sont (cas de BEH Alma).
- **Roubaix :** sur TOUT_ROUBAIX, le revenu médian et le taux de pauvreté sont les vrais chiffres de la commune (Filosofi 2023, dans `roubaix_commune.yml`). Ils ne sont pas comparables avec ceux des CQ, car l'Insee a changé de méthode entre 2021 et 2023.
- **Demandeurs d'emploi / 15-64 ans :** les DEFM France Travail sont rapportés à la population du recensement. Les millésimes diffèrent, c'est donc un ordre de grandeur.
- **Millésimes mélangés :** une « année » regroupe des sources de dates différentes (en 2023 : recensement 2023, revenus 2021, CAF et DEFM 2024, RPLS, BPE 2025). Chaque en-tête indique sa source et son année.

L'onglet **Méthode** du classeur détaille le calcul de chaque indicateur.

## Rattacher les IRIS aux CQ

Le fichier `data/ref/cq_iris.yml` donne la liste des IRIS de chaque CQ. Pour changer un rattachement, il suffit de déplacer un code IRIS d'une liste à l'autre, puis de relancer le script. Pour créer un CQ, il suffit d'ajouter une ligne : sa page récap est créée automatiquement.

Un IRIS absent de toutes les listes est compté dans « Hors CQ » : il reste dans le total de Roubaix, mais n'a ni ligne ni contour propre. En 2023, 7 IRIS sont dans ce cas (Fosse aux Chênes, Cul de Four, Barbieux-Vauban, Barbieux Sud, Trois Ponts Nord, Trois Ponts Sud, Fraternité). Pour leur donner une ligne, mettre `AFFICHER_HORS_CQ = True` dans `portrait_cq.py`.

## Équipements (BPE)

Le thème Équipements compte les équipements de la BPE par IRIS, puis par CQ. Le fichier `BPE<AA>_Roubaix_equipements_officiel.xlsx` (onglet `BPE`, colonnes « Code Type d'équipement » et « Code IRIS ») se dépose dans `data/brut`. Si plusieurs millésimes sont présents, le plus récent est pris, et son année s'affiche dans les en-têtes (« BPE 2025 »).

Les catégories sont définies dans `BPE_GROUPES`, en haut de `portrait_cq.py`, avec les codes Insee (« C201 » = collège) ou des préfixes (« F1 » = tous les équipements sportifs). La liste des codes est dans l'onglet « Dictionnaire Insee » du fichier BPE. Pour ajouter une catégorie : l'ajouter dans `BPE_GROUPES`, puis ajouter une ligne dans `INDICATEURS` (onglet Équipements) et, si besoin, dans `CHIFFRES_CLES` (pages récap).

Points à connaître :
- La BPE donne un nombre d'établissements, pas leur taille : une crèche de 10 places compte autant qu'une crèche de 60 places.
- Le thème ne contient que des comptages directs de la BPE, sans ratio par habitant : la population du CQ figure à côté sur les pages récap.
- Les équipements dont l'Insee ne connaît pas l'IRIS (code `59512_IND`, surtout des artisans et des commerces) sont comptés dans Roubaix, mais dans aucun CQ.
- Les espaces verts ne sont pas dans la BPE : il faut une autre source (contours des parcs et jardins).

## Personnaliser la présentation

- **Modèle de page d'accueil :** `MODELE_ACCUEIL` dans `portrait_cq.py`. `"C"` affiche une colonne par thème (modèle par défaut), `"A"` un tableau de bord en tuiles et `"B"` un sommaire latéral. Les modèles sont dessinés dans `scripts/accueil.py`.
- **Chiffres clés affichés** sur l'accueil et les pages récap : liste `CHIFFRES_CLES` dans `portrait_cq.py`.
- **Indicateurs calculés** dans les onglets thématiques : liste `INDICATEURS` dans `portrait_cq.py`. Chaque ligne indique son thème, son libellé et sa règle de calcul (`somme`, `part`, `ratio`, `poids`, `evol`, `approche`).
- **Indicateurs communaux** plus récents que ceux par IRIS : `data/ref/roubaix_commune.yml`. Pour un nouveau millésime, il suffit d'y mettre à jour les valeurs.
