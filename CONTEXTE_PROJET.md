# CONTEXTE_PROJET.md — Journal de Continuité pour IA

> **Objectif** : Ce fichier documente l'état du projet, les décisions prises, les modifications effectuées et les tâches en cours.
> Il permet à un nouvel assistant IA de reprendre le travail sans perte de contexte.
> **Règle** : À chaque session de travail, ajouter une entrée datée en haut de la section « Historique des Sessions ».

---

## 1. Présentation du Projet

**Nom** : BDDMAS Roubaix – ApplicationMAJ  
**Dépôt Git** : GitHub (branche `main`)  
**Langage** : Python 3.14 + HTML/CSS/JS (vanilla)  
**Serveur** : FastAPI + Uvicorn  
**Usage** : Génération du classeur Excel BDDMAS (données infra-communales sur les 38 IRIS de Roubaix)

### Architecture simplifiée

```
ApplicationMAJ/
├─ main_bddmas.py              → Orchestrateur du pipeline ETL
├─ webapp.py                   → API FastAPI (gestion des jobs web)
├─ run_portal.bat / .py        → Lanceur du portail (double-clic, lance d'abord le transformer 2023)
├─ modules/
│  ├─ socle_geo.py             → Référentiel MAS, superficies, jointures
│  ├─ ingestion.py             → Pré-contrôle, lecture, nettoyage sources
│  ├─ lecture.py               → Lecture des données CSV (pandas) ou Parquet (DuckDB)
│  ├─ indicateurs.py           → Calculs dérivés, arrondis, répartitions
│  ├─ export_excel.py          → Remplissage du modèle Excel + mise en forme
│  ├─ pages_info.py            → Pages Présentation et Detail calcul générées selon le lot
│  ├─ mise_en_page.py          → Formats, largeurs, couleurs d'en-têtes, ordre des colonnes, volets figés
│  ├─ export_sig.py            → Export CSV pour SIG
│  ├─ persistence.py           → Insertion SQLAlchemy
│  ├─ colonnes_auto.py         → Colonnes inconnues d'un nouveau millésime (sans IA puis IA, cache YAML)
│  └─ llm_wrapper.py           → Wrapper OpenAI/Groq/Ollama
├─ dictionnaires/
│  ├─ files_names.yml          → Correspondances fichier → nom d'onglet
│  ├─ calculated_columns.yml   → Formules de colonnes calculées
│  ├─ info_pages.yml           → Titres des onglets (clés par thème, sans année)
│  ├─ liens_presentation.yml   → Liens INSEE de la page Présentation (par thème et millésime)
│  ├─ correspondances_auto.yml → Cache des décisions du module colonnes (généré, relisible, versionné)
│  ├─ millesimes_valides.yml   → Dernier millésime validé à la main par thème (créé au 1er lancement)
│  └─ meta/                    → Métadonnées CSV (meta2022/, meta2023/)
├─ scripts/
│  ├─ diag.py                  → Diagnostic des cubes INSEE 2023
│  ├─ extraire_indcvi_roubaix.py → Extraction FD_INDCVI Roubaix
│  ├─ transformer_2023_roubaix.py → Conversion cubes INSEE 2023 (lit data/data2023/sources_brutes_insee/)
│  └─ simuler_nouveau_millesime.py → Faux millésime +1 (libellés reformulés) pour tester colonnes_auto + IA
├─ doc/
│  ├─ etat_du_projet_bddmas.md → Rapport d'avancement détaillé
│  ├─ Fichiers_INSEE_2026.md   → Documentation fichiers INSEE
│  └─ r_gles_d_arrondis_compl_tes.md → Règles d'arrondis complètes
├─ archives/                   → Anciens scripts et fichiers archivés
├─ web/
│  ├─ index.html               → Page principale du portail
│  ├─ multi-upload.js          → Logique front (drag & drop, upload, suivi)
│  ├─ styles.css               → Feuille de style (charte Roubaix)
│  └─ logo_institutionnel.png  → Logo officiel Ville de Roubaix
├─ data/                       → Données brutes (NON versionnées)
├─ sorties/                    → Classeurs Excel générés (NON versionnés)
└─ TAB_BDDMAS_INSEE2022_MODELE.xlsx → Classeur modèle (gabarit)
```

---

## 2. Stack Technique & Dépendances Clés

| Composant | Détails |
|-----------|---------|
| Python | 3.14 (environnement virtuel `.venv`) |
| Backend | FastAPI, Uvicorn |
| Traitement | Pandas, OpenPyXL, DuckDB, PyYAML, tqdm |
| LLM (optionnel) | openai (SDK), python-dotenv |
| Front | HTML5/CSS3/JS vanilla (pas de framework) |
| Base (optionnel) | SQLAlchemy, configurable via `BDDMAS_DATABASE_URL` |

---

## 3. Conventions du Projet

- **Langue des commits** : Français
- **Langue du code** : Noms de variables/fonctions en français (ex: `arrondir_effectifs`, `executer_pipeline`)
- **Fichier de sortie** : va dans `sorties/` (ignoré par Git)
- **Fichier `.env`** : contient les clés API (Groq/OpenAI) — **JAMAIS versionné**
- **Métadonnées** : organisées par millésime dans `dictionnaires/meta/meta2022/` et `meta2023/`
- **Archives** : les anciens scripts/fichiers supprimés du dépôt vont dans `archives/`

---

## 4. Décisions Techniques Importantes

| Date | Décision | Raison |
|------|----------|--------|
| Oct 2026 | Déplacement des anciens fichiers meta du dépôt vers `archives/` + `dictionnaires/meta/meta2022/` | Fichiers CSV volumineux (>80k lignes chacun) qui polluaient le repo |
| Oct 2026 | Port fixe 5000 au lieu de port aléatoire | Compatibilité avec le script batch et prévisibilité |
| Oct 2026 | Fichier de sortie dans `sorties/` au lieu de la racine | Organisation et propreté du répertoire |
| Oct 2026 | Résolution dynamique des tables par thème (ex: `POP 2022` → `POP 2023`) | Compatibilité multi-millésime sans modifier les YAML |
| Oct 2026 | Charte graphique Roubaix (magenta `#e3006a`, ardoise `#1e293b`) | Identité visuelle officielle de la Ville |
| Oct 2026 | Ajout de `llm_wrapper.py` | Wrapper LLM générique (Groq/OpenAI/Ollama) pour futurs usages IA |
| 26/10/2026 | `run_portal.bat` lance `scripts/transformer_2023_roubaix.py` avant le portail (si cubes bruts présents) | Les cubes déposés dans `sources_brutes_insee/` sont convertis automatiquement, contrôle de cohérence visible au démarrage |
| 26/10/2026 | Onglet petite enfance nommé `PETITE ENFANCE {année du FD_INDCVI}` | Le millésime suit le fichier FD_INDCVI déposé, pas le recensement |
| 26/10/2026 | `info_pages.yml` indexé par thème (`POP`, `CAF`…) + fonction `titre_onglet()` | Titres corrects quel que soit le millésime de l'onglet |
| 26/10/2026 | `trouver_fichier_meta` lit aussi les sous-dossiers (`meta2022/`, `meta2023/`) et privilégie la méta de la même année | Ligne de commande fonctionnelle après le rangement des métas par millésime |
| 26/10/2026 | Pages Présentation et Detail calcul régénérées à chaque classeur (`modules/pages_info.py`) | Titre, années, dates et liens suivent le lot ; Detail calcul toujours aligné sur `calculated_columns.yml` |
| 26/10/2026 | Liens INSEE de la Présentation dans `liens_presentation.yml` (thème → année → URL) | Nouveau millésime = une ligne à ajouter, pas de modification du modèle Excel |
| 26/10/2026 | « Part des DEFM hommes/femmes » conservées rapportées à la population de l'IRIS | Choix de définition (part de la population), pas une erreur |
| 27/10/2026 | En-tête orange = indicateur sans total (taux, part, médiane, quartile, loyer…), bleu = effectif avec total ; bleues à gauche, orange à droite | Lecture plus simple : l'utilisateur sait où trouver les indicateurs, qu'ils soient calculés ou fournis par l'INSEE |
| 27/10/2026 | Ligne Total : `SUBTOTAL` gardé uniquement pour les colonnes additives (effectifs, superficie) | Une somme de taux ou de médianes n'a pas de sens |
| 27/10/2026 | Colonne « Crèches » retirée automatiquement si vide (`mise_en_page.py`), modèle Excel inchangé | Aucune source disponible (absente des deux versions de `Périmètres_MAS.csv`) |
| 27/10/2026 | Nombre de colonnes géo = position de « Libellé de l'Iris » (plus de `8 if "Age : 0"`) | Robuste au retrait de Crèches et aux évolutions du modèle |
| 27/10/2026 | Transformer 2023 sauté si les 10 fichiers produits existent, comptent 38 IRIS et sont plus récents que les sources et le script (`--force` pour recalculer) | Démarrage du portail en quelques secondes au lieu de relire les cubes INSEE |
| 27/10/2026 | Audit IRIS : le code commune seul « 59512 » (« Non localisé à l'iris ») n'est pas signalé comme inconnu | Ligne légitime du référentiel, pas une erreur |
| 27/10/2026 | Module `colonnes_auto.py` : colonne inconnue du modèle → correspondance exacte/normalisée, puis approchée (`difflib`, mêmes nombres et mêmes mots sensibles), puis IA (un appel par onglet, JSON validé) | Nouveau millésime intégré sans intervention ; l'IA ne touche jamais aux valeurs |
| 27/10/2026 | Décisions mises en cache dans `dictionnaires/correspondances_auto.yml` (`methode: manuel` = verrouillé) | Une variable n'est envoyée qu'une fois à l'IA ; correction humaine possible |
| 27/10/2026 | Module actif seulement pour un millésime plus récent que `millesimes_valides.yml` (créé au premier lancement avec le lot actuel) | Le lot 2022/2023 validé à la main reste strictement identique |
| 27/10/2026 | Sans clé / sans réseau : étape sans IA seule + avertissement ; seuil `BDDMAS_LLM_CONFIANCE_MIN` (0,8) | Le pipeline fonctionne toujours |
| 27/10/2026 | Données acceptées en CSV ou Parquet, mélangeables dans un lot ; lecture centralisée dans `modules/lecture.py` (Parquet via DuckDB, importé seulement si besoin) ; métadonnées toujours en CSV | Fichiers plus légers et plus rapides à lire (FD_INDCVI : 4 colonnes lues seulement), sans casser les lots CSV existants |
| 27/10/2026 | Indicateur dont une variable manque au millésime (`KeyError`) : message « Indicateur non calculé … variable absente de ce millésime », affiché en encadré jaune repliable dans le portail ; seules les autres erreurs de calcul restent en rouge et passent le job en « avec avertissements » | Les 13 indicateurs vides attendus en 2023 ne font plus croire à un échec |
| Oct 2026 | Suppression de `demarrer_portail.ps1` au profit de `run_portal.bat` + `run_portal.py` | Simplification : un seul clic, pas de politique d'exécution PowerShell |

---

## 5. Limites Connues & Points d'Attention

- **Recensement 2023** : certaines variables absentes des cubes INSEE (salariés CDI, familles monoparentales, pop 60-74 ans) → indicateurs vides dans le classeur
- **Liens Présentation** : une année absente de `liens_presentation.yml` garde le lien du modèle Excel (à compléter à chaque nouveau millésime)
- **Formule « actifs travaillant dans la commune de résidence »** : divise par « Salariés 15 ans ou plus » au lieu de « Actifs occupés 15 ans ou plus » ; sans effet en 2023 (variable absente), à revoir si un millésime la contient
- **Colonne « Crèches »** (onglet petite enfance) : aucune source ; retirée du classeur tant qu'elle est vide. Si une source arrive, la renseigner suffit : la colonne réapparaît
- **Transformer 2023** : après remplacement d'un CSV INSEE, la date de modification déclenche le recalcul ; en cas de doute, `python scripts/transformer_2023_roubaix.py --force`
- **Couleurs d'en-têtes** : déterminées par `_est_additive()` de `mise_en_page.py` (règles d'arrondi + mots-clés) ; une nouvelle colonne mal classée se corrige là
- **Ligne de commande** : `python main_bddmas.py` lit `data/` à plat ; depuis le rangement par sous-dossiers, le portail est le mode recommandé
- **Écarts d'arrondi** : totaux du classeur légèrement inférieurs au contrôle du transformer (ex. 98 284 vs 98 286 habitants) car arrondi par IRIS
- **Exports SIG et SQL** : disponibles uniquement en ligne de commande, pas depuis le portail web
- **Colonnes auto** : une décision fausse se corrige dans `dictionnaires/correspondances_auto.yml` (changer `entete`, mettre `methode: manuel`). Une colonne « non résolue » garde son libellé méta. Le premier lot traité avec l'IA envoie aussi les colonnes absentes du modèle 2022 (une seule fois, ensuite cache)
- **Accès IA bloqué au bureau** : depuis le poste de la mairie, toute connexion HTTPS vers une API d'IA (Groq, Mistral…) est coupée pendant la poignée de main TLS, même en partage de connexion (filtrage côté poste). Au bureau : `BDDMAS_LLM=0` dans `.env` ; le module garde correspondance exacte, approchée et cache, les colonnes restantes sont « non résolues » à corriger dans `correspondances_auto.yml`. IA utilisable hors du poste de la mairie (ex. à domicile), sans changement de code
- **Avertissement UNC** : « Les chemins d'accès UNC ne sont pas pris en charge » au démarrage → sans conséquence

---

## 6. Historique des Sessions de Travail

### 📅 27 octobre 2026 (fin) — Données au format Parquet

**Auteur** : Bilal (assisté par IA)

#### Modifications effectuées
- `modules/lecture.py` (nouveau, remplace l'ébauche `modules/utils.py`) : `est_fichier_donnees`, `lire_entetes`, `lire_table`, `lire_par_blocs`, `compter_lignes` ; CSV par pandas comme avant, Parquet par DuckDB (colonnes demandées seulement, types `str`/`float64` convertis par DuckDB, erreurs DuckDB transformées en `ValueError`)
- `modules/ingestion.py` : pré-contrôle (en-têtes, audit IRIS désormais aussi pour les Parquet), ingestion des thèmes et lecture par blocs du FD_INDCVI passent par `lecture.py` ; correction du nom de base (`fichier[:-4]` → `os.path.splitext`) qui cassait l'année et le thème des `.parquet`
- `modules/socle_geo.py` : `Périmètres_MAS` lisible en Parquet
- `webapp.py`, `web/multi-upload.js`, `web/index.html` : zone Données accepte `.parquet` ; une méta en Parquet est refusée avec un message clair
- `requirements.txt` : ajout de `duckdb`

#### Vérifications
- Lots d'exemple 2022 et 2023 convertis en Parquet (tout en texte, typé, et mélange CSV/Parquet) : classeurs identiques cellule par cellule au lot CSV (14 onglets), pré-contrôle identique (IRIS 38/38)
- Portail (API) : lot mixte → « Prêt » puis classeur généré ; méta `.parquet` refusée ; Parquet corrompu → erreur de pré-contrôle `csv_illisible`, pas de plantage
- `scripts/transformer_2023_roubaix.py` : cubes bruts lus en CSV ou en Parquet (`chemin_source()`, Parquet préféré, filtrage Roubaix fait par DuckDB) ; `run_portal.bat` lance aussi le transformer si seuls des Parquet sont présents. Testé sur un cube synthétique (mêmes lignes en CSV et en Parquet typé) ; à valider sur les vrais cubes Insee avec `--force`
- Non traité : `scripts/simuler_nouveau_millesime.py` reste en CSV

### 📅 27 octobre 2026 (suite) — Module colonnes inconnues (IA)

**Auteur** : Bilal (assisté par IA)

#### Modifications effectuées
- `modules/colonnes_auto.py` (nouveau) : références par thème (ligne 2 du modèle + `var1..var4` de `calculated_columns.yml`, indicateurs calculés exclus) ; correspondance exacte normalisée (« Population de 0 à 14 ans » = « Pop 0-14 ans », casse, « et plus » / « ou plus », « (princ) », « en 2022 ») ; approchée `difflib` ≥ 0,92 si mêmes nombres et mêmes mots sensibles (hommes/femmes…) ; IA pour le reste (correspondance, nouvel en-tête, `additive`, `precision`, confiance) ; cache `correspondances_auto.yml` ; `resumer_decisions()` pour le pré-contrôle
- `modules/llm_wrapper.py` : client créé au premier appel (l'import ne plante plus sans clé), `llm_disponible()`, options `systeme` et `format_json`
- `modules/ingestion.py` : `ingerer_donnees_thematiques(..., chemin_modele, chemin_calculs, decisions_colonnes)` appelle le module par onglet
- `modules/indicateurs.py` / `modules/mise_en_page.py` : `_precision_arrondi` et `_est_additive` utilisent d'abord les règles du module pour les colonnes qu'il a créées
- `modules/export_excel.py` : alias DEFM et renommages CNAM sortis en constantes (`ALIAS_ENTETES_DEFM`, `RENOMMAGES_CNAM`) pour être réutilisés
- `main_bddmas.py` : décisions dans `rapport_precontrole["colonnes_auto"]`, avertissement `colonnes_auto` par onglet, clé `colonnes_auto` dans le résultat
- `.env.example` (nouveau)
- `scripts/simuler_nouveau_millesime.py` (nouveau) : copie le lot dans un dossier temporaire, avance d'un an les `base-ic-*`, reformule des libellés méta et en retire un, lance le pipeline avec une copie de `dictionnaires/` ; sorties dans `sorties/simulation/` (classeur, `decisions.json`, cache simulé), vrai dépôt intact
- `dictionnaires/millesimes_valides.yml` (généré au premier lancement) : le module ne s'active que pour un millésime plus récent ; le lot actuel n'est pas modifié

#### Vérifications
- Lot de test 2024 simulé (POP) : 4 rattachements sans IA, Hommes/Femmes jamais confondus, IA simulée : 1 rattachement, 1 nouvelle colonne (précision 0, bleue), 1 non résolue (confiance 0,5) ; relance = 0 appel IA (cache)
- Millésime ≤ validé : colonnes identiques à avant, 0 appel IA
- Simulation 2024 avec Groq (codes renommés) : 16 rattachements sans IA, 18 par l'IA ; corrigé ensuite : références enrichies des noms du classeur validé (codes de la méta du millésime validé passés dans `preparer_colonnes_thematiques`, donc YAML puis méta, exactement comme au traitement validé ; la méta seule donnait de faux noms, ex. « Pop non scol 15 ans ou plus Aucun diplôme ou CEP »), glossaire des codes INSEE dans la consigne, réponse IA tolérante aux petites variantes, 5 essais sur erreur 429 (quota Groq)
- Simulation 5 : POP sans écart ; ensuite : « Nombre de » ignoré à la comparaison, consigne IA « reprendre l'en-tête existant », nouvel en-tête proche d'un existant ramené à l'existant, variable sans libellé méta : confiance 0,95 exigée et jamais de nom inventé, 3 essais par lot sur coupure réseau
- Portail : `executer_pipeline(..., dossier_dicos_reference)` ; `webapp.py` passe le vrai `dictionnaires/` (le job travaille sur une copie sans méta) → cache et millésimes validés persistants ; tableau « Colonnes renommées ou ajoutées automatiquement » sous le classeur généré (`index.html`, `multi-upload.js`, champ `colonnes_auto` du job)
- Classeur du lot actuel régénéré avec le module : identique à l'original (14 onglets, valeurs, formats, couleurs, largeurs, tableaux)
- Sans clé : import OK, pipeline continue, avertissement « IA non configurée »


### 📅 27 octobre 2026 — Audit IRIS, mise en page Excel, démarrage rapide

**Auteur** : Bilal (assisté par IA)

#### Modifications effectuées
- `modules/ingestion.py` : audit des IRIS au pré-contrôle (`_charger_iris_reference`, `_iris_roubaix_presents`, `_auditer_iris`) ; signale les IRIS manquants ou inconnus par source, en ignorant « 59512 » seul
- `modules/mise_en_page.py` (nouveau, appelé après `mettre_a_jour_pages_info` dans `export_excel.py`) :
  - formats de nombres selon `_precision_arrondi`, décimales affichées limitées à celles de la source (RPLS : 9,3 et non 9,30)
  - ligne Total : `SUBTOTAL` conservé seulement pour les colonnes additives
  - en-têtes orange pour les indicateurs, bleus pour les effectifs ; colonnes bleues regroupées à gauche, orange à droite (valeurs, styles, tableau Excel et `SUBTOTAL` déplacés ensemble)
  - largeurs calculées mot par mot (en-têtes sur 5 lignes max, bouton de filtre compris) ; colonnes de texte (« Incertitude… » REV DEC/REV DISP) élargies à 2 lignes max par IRIS
  - colonne « Crèches » vide supprimée (tableau, largeurs, `SUBTOTAL` recalés) ; vue réinitialisée en A1 et volet figé après « Libellé de l'Iris »
- `scripts/transformer_2023_roubaix.py` : `sorties_a_jour()` + option `--force` ; la transformation est sautée si rien n'a changé

#### Vérifications
- Arrondis : aucune colonne du classeur 9 ne dépasse sa règle (`doc/r_gles_d_arrondis_compl_tes.md`) → conforme
- Mise en page testée sur le classeur 9 : 12 onglets, valeurs identiques par en-tête après déplacement, tableaux Excel et totaux cohérents
- Crèches : absente du `Périmètres_MAS.csv` actuel et de celui de l'ancien alternant → pas de source

### 📅 26 octobre 2026 (fin d'après-midi) — Pages Présentation et Detail calcul dynamiques

**Auteur** : Bilal (assisté par IA)

#### Modifications effectuées
- `modules/pages_info.py` (nouveau) : `mettre_a_jour_pages_info()` appelée juste avant l'enregistrement du classeur
  - **Présentation** : titre `Base MAS - INSEE mise à jour {année POP}`, colonne Année = millésime réel de chaque onglet (« Non fourni » si thème absent), dates colonne C mises à l'année du fichier, lien colonne E pris dans `liens_presentation.yml`
  - **Detail calcul** : reconstruit depuis `calculated_columns.yml` (une colonne par thème, `Indicateur -> formule` avec les vrais noms de colonnes) ; indicateurs non calculés en rouge italique « non calculé : variable absente de ce millésime » ; largeur 42, hauteurs de ligne calculées, anciens styles effacés
- `dictionnaires/liens_presentation.yml` (nouveau) : liens 2022 du modèle + liens RP 2023 (POP 9054332, ACT RES 9040859, COU FAM 9058978, DIP 9054820, LOG 9061333) + CAF 8682393, CNAM 8736938, RPLS 8736658 (source : `doc/Fichiers_INSEE_2026.md`)
- `modules/export_excel.py` : paramètre `chemin_calculs` ajouté à `generer_fichier_bddmas` et `_generer_depuis_modele`, appel de `mettre_a_jour_pages_info`
- `main_bddmas.py` : transmet `chemin_calculs` à `generer_fichier_bddmas`
- `dictionnaires/calculated_columns.yml` : « Part des DEFM ABC de niveau ≤ au BAC dans les DEFM ABC (%) » corrigée (`* 100` manquant, valeurs 0,8 → 80 %)

#### Résultat
- Validé sur le lot 2023 : Présentation « mise à jour 2023 », années 2023/2021/2022/2024/2025, liens à jour ; Detail calcul lisible, 13 indicateurs non calculés signalés en rouge

### 📅 26 octobre 2026 (après-midi) — Validation 2023 et millésimes dynamiques

**Auteur** : Bilal (assisté par IA)

#### Validation bout-en-bout (portail, lot complet 2023)
- Transformer : 38 IRIS, cohérence OK (Population 98 286, Logements 43 709, Résidences principales = Ménages 39 257, Pop 15-64 = Actifs + Inactifs 62 551)
- Pré-contrôle « Prêt » : 11 thèmes, 1 périmètre, 1 fichier enfants, toutes les métas associées
- Classeur : 14 onglets, 38 IRIS par onglet, aucun en-tête `Column…`/vide, tableaux structurés bornés à la ligne 40
- 13 avertissements attendus (variables absentes des cubes 2023 : salariés/CDI, commune de résidence, familles, pop 60-74 ans)

#### Modifications effectuées
- `run_portal.bat` : exécute `scripts/transformer_2023_roubaix.py` après activation du `.venv` si `data/data2023/sources_brutes_insee/base-ic-*-2023.csv` existe ; en cas d'échec, pause puis lancement du portail quand même
- `scripts/transformer_2023_roubaix.py` : `DOSSIER_RACINE` remonte d'un niveau (script déplacé dans `scripts/`)
- `main_bddmas.py` : onglet `PETITE ENFANCE {millésime du FD_INDCVI}` (au lieu de `PETITE ENFANCE 2022` en dur)
- `modules/export_excel.py` : nouvelle fonction `titre_onglet()` (titre trouvé par thème, année ignorée) utilisée partout ; renommage de l'onglet modèle petite enfance corrigé (« PETITE ENFANCE MILLÉSIME » exclu du décompte du thème) ; `creer_modele_si_absent` ordonne les onglets par thème sans années en dur
- `dictionnaires/info_pages.yml` : clés sans année (`POP`, `ACT RES`, …, `PETITE ENFANCE`, `PETITE ENFANCE MILLÉSIME`)
- `modules/ingestion.py` : `trouver_fichier_meta` parcourt les sous-dossiers directs et privilégie la méta de même année que le fichier source

#### Résultat
- Titres réels en ligne 1 de chaque onglet (ex. POP 2023 → « Données infra-communales - Population »)
- À savoir : après toute modification du code, fermer la fenêtre du portail et relancer `run_portal.bat` (le serveur ne recharge pas le code)

### 📅 26 octobre 2026 — Mise à jour majeure du dépôt Git

**Auteur** : Bilal (assisté par IA)

#### Modifications effectuées :

**Nettoyage du dépôt :**
- Suppression des anciens fichiers de métadonnées CSV volumineux de la racine de `dictionnaires/meta/` (>500k lignes au total)
- Archivage des anciens scripts dans `archives/` (TAB_BDDMAS_INSEE2022.py, demarrer_portail.ps1, run_portal.spec, traitement_enfants_roubaix.ipynb, prgrms_ancien_alternant/)
- Suppression du fichier `r_gles_d_arrondis_compl_tes.md` de la racine (déplacé dans `doc/`)
- Réorganisation des métadonnées par millésime (`meta2022/`, `meta2023/`)

**Pipeline ETL (`modules/`) :**
- `indicateurs.py` : Ajout de la résolution dynamique des tables par thème (`_resoudre_table()`) — permet au pipeline de fonctionner avec 2022 ou 2023 sans modifier les YAML de calcul. Les expressions dans `calculated_columns.yml` qui référencent `files["POP 2022"]` sont automatiquement réécrites si seul `POP 2023` est disponible.
- `export_excel.py` : Gestion améliorée des colonnes nouvelles (insertion avant « Superficie en km² » avec copie de style), nettoyage des colonnes vides en fin de feuille, recalcul correct des plages de tableaux structurés.
- `main_bddmas.py` : Chemin de sortie redirigé vers `sorties/`

**Portail web :**
- `run_portal.py` : Réécriture complète en français, attente active du serveur avant ouverture du navigateur (polling HTTP avec timeout 30s), gestion des arrêts prématurés
- `run_portal.bat` : Vérification de l'existence du virtualenv, suppression du polling PowerShell, gestion d'erreur avec pause
- `web/index.html` : Logo institutionnel, favicon, indicateurs de statut dynamiques (remplacent les anciens boutons codés en dur), barre de progression pour l'analyse
- `web/multi-upload.js` : 13 fichiers de données + 12 métadonnées avec détection robuste (insensible casse/accents), barre de progression XHR avec pourcentage et volume, gestion d'erreur améliorée
- `web/styles.css` : Refonte complète avec charte Roubaix (magenta #e3006a, ardoise #1e293b), logo institutionnel, badge « PORTAIL DATA SIG »

**Nouveaux fichiers :**
- `modules/llm_wrapper.py` : Wrapper LLM générique compatible OpenAI/Groq/Ollama
- `web/logo_institutionnel.png` : Logo officiel Ville de Roubaix
- `scripts/` : Scripts utilitaires (diag.py, extraire_indcvi, transformer_2023)
- `doc/` : Documentation projet (état du projet, fichiers INSEE, règles d'arrondis)
- `dictionnaires/meta/meta2022/` et `meta2023/` : Métadonnées organisées par millésime

**Configuration :**
- `requirements.txt` : Simplifié (dotenv, openai, pandas, pyyaml, openpyxl, tqdm)
- `.gitignore` : Ajout de `.env`, `.gitmessage`, `sorties/`, fichiers IDE, fichiers sensibles, bases locales
- `README.md` : Réécriture complète avec architecture détaillée, guide d'installation, documentation du pipeline, limitations connues

---

## 7. Tâches à Faire (TODO)

- [x] Validation bout-en-bout du portail avec données réelles 2023 (26/10)
- [x] Adapter les deux premières pages en fonction des données (2022, 2023, nouveaux calculs, etc) (26/10)
- [x] Harmoniser les arrondis selon les directives strictes (vérifié conforme le 27/10)
- [x] Audit de complétude des 38 IRIS roubaisiens avant traitement (27/10)
- [x] Mise en page Excel automatisée (largeurs auto, séparateurs de milliers, couleurs, ordre des colonnes) (27/10)
- [x] Dynamiser le nom de l'onglet petite enfance selon le millésime (26/10)
- [x] Titres d'onglets indépendants du millésime (`info_pages.yml`) (26/10)
- [ ] Source pour la colonne « Crèches » de l'onglet petite enfance (retirée tant qu'elle est vide)
- [x] Transformer 2023 sauté si déjà à jour (27/10)
- [x] `.gitignore` : `data/`, `meta2022/`, `meta2023/` et `sources_brutes_meta/` exclus (27/10)
- [x] Intégrer le module LLM dans le pipeline : colonnes inconnues rattachées ou créées automatiquement (27/10)
- [x] Afficher les décisions `colonnes_auto` dans le portail (27/10)
- [ ] Tester l'IA hors poste mairie (simulation `scripts/simuler_nouveau_millesime.py`), réseau bloqué au bureau
- [ ] Chatbot du portail (chantier séparé, même blocage réseau au bureau)

---

## 8. Comment Reprendre le Travail

1. **Lire ce fichier** pour comprendre l'état du projet
2. **Lire `doc/etat_du_projet_bddmas.md`** pour le rapport d'avancement détaillé
3. **Lire `README.md`** pour l'architecture et les instructions d'utilisation
4. **Consulter `doc/r_gles_d_arrondis_compl_tes.md`** pour les règles métier
5. **Tester le portail** : double-cliquer sur `run_portal.bat`
6. **Après toute modification** : mettre à jour la section « Historique des Sessions » ci-dessus
