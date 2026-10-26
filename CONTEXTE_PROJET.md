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
├─ run_portal.bat / .py        → Lanceur du portail (double-clic)
├─ modules/
│  ├─ socle_geo.py             → Référentiel MAS, superficies, jointures
│  ├─ ingestion.py             → Pré-contrôle, lecture, nettoyage sources
│  ├─ indicateurs.py           → Calculs dérivés, arrondis, répartitions
│  ├─ export_excel.py          → Remplissage du modèle Excel + mise en forme
│  ├─ export_sig.py            → Export CSV pour SIG
│  ├─ persistence.py           → Insertion SQLAlchemy
│  └─ llm_wrapper.py           → Wrapper OpenAI/Groq/Ollama (nouveau)
├─ dictionnaires/
│  ├─ files_names.yml          → Correspondances fichier → nom d'onglet
│  ├─ calculated_columns.yml   → Formules de colonnes calculées
│  ├─ info_pages.yml           → Infos des pages du classeur
│  └─ meta/                    → Métadonnées CSV (meta2022/, meta2023/)
├─ scripts/
│  ├─ diag.py                  → Diagnostic des cubes INSEE 2023
│  ├─ extraire_indcvi_roubaix.py → Extraction FD_INDCVI Roubaix
│  └─ transformer_2023_roubaix.py → Conversion cubes INSEE 2023
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
| Oct 2026 | Suppression de `demarrer_portail.ps1` au profit de `run_portal.bat` + `run_portal.py` | Simplification : un seul clic, pas de politique d'exécution PowerShell |

---

## 5. Limites Connues & Points d'Attention

- **Recensement 2023** : certaines variables absentes des cubes INSEE (salariés CDI, familles monoparentales, pop 60-74 ans) → indicateurs vides dans le classeur
- **Onglet petite enfance** : s'appelle toujours `PETITE ENFANCE 2022` quel que soit le millésime (nom codé en dur)
- **Exports SIG et SQL** : disponibles uniquement en ligne de commande, pas depuis le portail web
- **Avertissement UNC** : « Les chemins d'accès UNC ne sont pas pris en charge » au démarrage → sans conséquence

---

## 6. Historique des Sessions de Travail

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

- [ ] Validation bout-en-bout du portail avec données réelles 2023
- [ ] Adapter les deux premières pages en fonction des données (2022, 2023, nouveaux calculs, etc)
- [ ] Harmoniser les arrondis selon les directives strictes (cf. `doc/r_gles_d_arrondis_compl_tes.md`)
- [ ] Audit de complétude des 38 IRIS roubaisiens avant traitement
- [ ] Mise en page Excel automatisée (largeurs auto, séparateurs de milliers)
- [ ] Dynamiser le nom de l'onglet petite enfance selon le millésime
- [ ] Intégrer le module LLM dans le pipeline (ex: Si des colonnes avec un nom non explicite, alors l'ia définit cette colonne pour permettre de mieux l'intégrer)

---

## 8. Comment Reprendre le Travail

1. **Lire ce fichier** pour comprendre l'état du projet
2. **Lire `doc/etat_du_projet_bddmas.md`** pour le rapport d'avancement détaillé
3. **Lire `README.md`** pour l'architecture et les instructions d'utilisation
4. **Consulter `doc/r_gles_d_arrondis_compl_tes.md`** pour les règles métier
5. **Tester le portail** : double-cliquer sur `run_portal.bat`
6. **Après toute modification** : mettre à jour la section « Historique des Sessions » ci-dessus
