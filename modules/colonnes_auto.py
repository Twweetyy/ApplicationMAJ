"""Colonnes inconnues d'un nouveau millésime : rattachement à un en-tête connu ou nouvelle colonne.

Ordre : cache YAML, correspondance sans IA (exacte puis approchée), puis IA pour le reste.
L'IA ne produit jamais de valeurs : seulement des noms et des règles (additive, précision).
Sans clé API ou sans réseau, seule l'étape sans IA s'applique et le pipeline continue.
"""
import difflib
import json
import os
import re
import time
import unicodedata
from datetime import date

import yaml

NOM_CACHE = "correspondances_auto.yml"
NOM_MILLESIMES_VALIDES = "millesimes_valides.yml"
ENTETE_MILLESIMES_VALIDES = (
    "# Dernier millésime traité et validé à la main, par thème (créé au premier lancement).\n"
    "# Le module colonnes_auto ne touche pas un fichier de ce millésime ou plus ancien :\n"
    "# il ne s'active que pour un millésime plus récent (ou un thème absent de cette liste).\n"
)
ENTETE_CACHE = (
    "# Généré par modules/colonnes_auto.py : une entrée par variable source (clé sans millésime).\n"
    "# Pour corriger une décision : modifier « entete » (ou additive / precision) puis mettre\n"
    "# « methode: manuel » ; l'entrée ne sera plus jamais recalculée.\n"
)
SEUIL_APPROCHE = 0.92
ECART_AMBIGU = 0.02
TAILLE_LOT_LLM = 40
ESSAIS_LLM = 2
CONFIANCE_SANS_LIBELLE = 0.95
FEUILLES_FIXES = {"Présentation", "Detail calcul"}
# Colonnes ajoutées par le pipeline (périmètre, superficies, petite enfance) : jamais une cible
ENTETES_HORS_SOURCE = {"Superficie en km²", "TOTAL 0-17", "Crèches"}
COLONNES_GEO = {"IRIS", "COM", "TYP_IRIS", "LAB_IRIS", "CODGEO"}
COLONNES_TECHNIQUES = {
    "iris", "com", "typ iris", "lab iris", "commune ou arm", "type d iris", "label de l iris",
    "code geographique", "code commune", "libelle geographique", "libelle de la commune",
    "note", "note de diffusion",
}
# « Nombre de » n'apporte rien : « Nombre de rés princ 3 pièces » = « Rés princ 3 pièces »
MOTS_VIDES = {"de", "des", "du", "la", "le", "les", "l", "d", "en", "au", "aux", "a", "et", "nombre", "nb"}
# Deux libellés qui diffèrent sur l'un de ces mots ne sont jamais rapprochés sans IA
MOTS_SENSIBLES = {
    "homme", "femme", "moin", "plu", "hor", "non", "san", "avec", "francai", "etranger", "immigre",
    "proprietaire", "locataire", "vacant", "actif", "inactif", "occupe", "chomeur", "salarie",
    "scol", "scolarise", "menage", "famille", "couple", "maison", "appartement", "hlm", "enfant",
    "monoparentale", "seul", "princ", "secondaire", "occasionnel",
}

# Règles (additive, précision) des colonnes créées par le module, par (thème, en-tête normalisé)
_REGLES: dict[tuple[str, str], dict] = {}


def _theme(nom_onglet: str) -> str:
    return re.sub(r"\s+\d{4}$", "", str(nom_onglet)).strip()


def _sans_accents(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", str(texte).casefold())
    return "".join(caractere for caractere in texte if not unicodedata.combining(caractere))


def _normaliser_simple(texte) -> str:
    """Même normalisation que export_excel._normaliser_nom_colonne."""
    texte = re.sub(r"[^a-z0-9]+", " ", _sans_accents(texte))
    return re.sub(r"\s+", " ", texte).strip()


def _normaliser(texte) -> str:
    """Normalisation large pour comparer deux libellés INSEE formulés différemment."""
    texte = _sans_accents(texte)
    texte = re.sub(r"\([^)]*\)", " ", texte)            # « (princ) », « (ex-CMUC) »
    texte = re.sub(r"\ben \d{4}\b", " ", texte)          # « Pop 15-24 ans en 2022 »
    texte = re.sub(r"\bet plus\b", "ou plus", texte)
    texte = re.sub(r"\bpopulation\b", "pop", texte)
    texte = re.sub(r"\bresidences? principales?\b", "res princ", texte)
    texte = re.sub(r"[^a-z0-9]+", " ", texte)
    mots = []
    for mot in texte.split():
        if mot in MOTS_VIDES:
            continue
        # Pluriel simple : « ménages » = « ménage »
        mots.append(mot[:-1] if len(mot) > 3 and mot.endswith(("s", "x")) else mot)
    return " ".join(mots)


def _signature(texte) -> tuple[str, tuple, frozenset]:
    norme = _normaliser(texte)
    mots = norme.split()
    return norme, tuple(mot for mot in mots if mot.isdigit()), frozenset(mot for mot in mots if mot in MOTS_SENSIBLES)


def _est_technique(code: str, nom: str) -> bool:
    return str(code).upper() in COLONNES_GEO or _normaliser_simple(nom) in COLONNES_TECHNIQUES


def _cle_variable(code_source: str, theme: str) -> str:
    """Code sans millésime : P24_POP0014 -> POP0014, DEC_MED21 -> DEC_MED (Filosofi)."""
    code = re.sub(r"^[A-Z]\d{2}_", "", str(code_source).strip())
    if theme.startswith("REV"):
        code = re.sub(r"\d{2}$", "", code)
    return code


# --------------------------------------------------------------------------- références


def charger_references(chemin_modele: str | None, chemin_calculs: str | None) -> dict[str, list[str]]:
    """En-têtes connus par thème : ligne 2 du modèle + variables de calculated_columns.yml."""
    references: dict[str, list[str]] = {}
    indicateurs = set()
    calculs = {}
    if chemin_calculs and os.path.isfile(chemin_calculs):
        with open(chemin_calculs, "r", encoding="UTF-8") as fichier:
            calculs = yaml.safe_load(fichier) or {}
        indicateurs = {str(nom).strip() for nom in calculs}

    def ajouter(theme, entete):
        if entete is None:
            return
        entete = str(entete).strip()
        if not entete or entete in indicateurs or entete in ENTETES_HORS_SOURCE:
            return
        liste = references.setdefault(theme, [])
        if entete not in liste:
            liste.append(entete)

    if chemin_modele and os.path.isfile(chemin_modele):
        from openpyxl import load_workbook

        classeur = load_workbook(chemin_modele, read_only=True)
        try:
            for feuille in classeur.worksheets:
                if feuille.title in FEUILLES_FIXES or feuille.title.startswith("PETITE ENFANCE"):
                    continue
                entetes = next(feuille.iter_rows(min_row=2, max_row=2, values_only=True), ())
                entetes = list(entetes)
                if "Libellé de l'Iris" in entetes:
                    entetes = entetes[entetes.index("Libellé de l'Iris") + 1:]
                theme = _theme(feuille.title)
                for entete in entetes:
                    ajouter(theme, entete)
        finally:
            classeur.close()
        # Renommages faits ensuite par export_excel : on vise le nom attendu par l'export
        from .export_excel import ALIAS_ENTETES_DEFM, RENOMMAGES_CNAM
        if "DEFM" in references:
            references["DEFM"] = [
                ALIAS_ENTETES_DEFM.get(_normaliser_simple(entete), entete) for entete in references["DEFM"]
            ]
        if "CNAM" in references:
            for libelle_donnees in RENOMMAGES_CNAM:
                ajouter("CNAM", libelle_donnees)

    for params in calculs.values():
        if not isinstance(params, dict) or not params.get("df"):
            continue
        theme_defaut = _theme(params["df"])
        expression = str(params.get("expression") or "")
        # files["POP 2022"][var1] : var1 appartient au thème POP
        themes_variables = {
            variable: _theme(table)
            for table, variable in re.findall(r"""files\[\s*["']([^"']+)["']\s*\]\[\s*(var\d)\s*\]""", expression)
        }
        for variable in ("var1", "var2", "var3", "var4"):
            if params.get(variable):
                ajouter(themes_variables.get(variable, theme_defaut), params[variable])
    return references


# --------------------------------------------------------------------------- millésimes validés


def charger_millesimes_valides(dossier_dicos: str) -> dict | None:
    """{thème: millésime} validés à la main, ou None si le fichier n'existe pas encore."""
    chemin = os.path.join(dossier_dicos, NOM_MILLESIMES_VALIDES)
    if not os.path.isfile(chemin):
        return None
    try:
        with open(chemin, "r", encoding="UTF-8") as fichier:
            return {str(theme): str(annee) for theme, annee in (yaml.safe_load(fichier) or {}).items()}
    except (OSError, yaml.YAMLError, AttributeError) as erreur:
        print(f"Attention : {NOM_MILLESIMES_VALIDES} illisible ({erreur}), module colonnes désactivé.")
        return {"*": "9999"}


def enregistrer_millesimes_valides(dossier_dicos: str, millesimes: dict) -> None:
    chemin = os.path.join(dossier_dicos, NOM_MILLESIMES_VALIDES)
    with open(chemin, "w", encoding="UTF-8") as fichier:
        fichier.write(ENTETE_MILLESIMES_VALIDES)
        yaml.safe_dump(millesimes, fichier, allow_unicode=True, sort_keys=False)


def millesime_a_traiter(theme: str, annee: str | None, millesimes_valides: dict) -> bool:
    """Vrai si le fichier est plus récent que le dernier millésime validé de son thème."""
    reference = millesimes_valides.get(theme, millesimes_valides.get("*"))
    if reference is None:
        return True
    try:
        return int(annee) > int(reference)
    except (TypeError, ValueError):
        return False


def _cle_fichier(nom: str) -> str:
    """Nom de fichier comparable : sans extension, préfixe meta_/data_, année, accents ni ponctuation."""
    nom = os.path.splitext(os.path.basename(str(nom)))[0]
    nom = re.sub(r"^(meta|data)_", "", nom, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\d{4}", "", _sans_accents(nom)))


# --------------------------------------------------------------------------- cache


def charger_cache(dossier_dicos: str) -> dict:
    chemin = os.path.join(dossier_dicos, NOM_CACHE)
    if not os.path.isfile(chemin):
        return {}
    try:
        with open(chemin, "r", encoding="UTF-8") as fichier:
            return yaml.safe_load(fichier) or {}
    except (OSError, yaml.YAMLError) as erreur:
        print(f"Attention : {NOM_CACHE} illisible ({erreur}), cache ignoré.")
        return {}


def enregistrer_cache(dossier_dicos: str, cache: dict) -> None:
    chemin = os.path.join(dossier_dicos, NOM_CACHE)
    with open(chemin, "w", encoding="UTF-8") as fichier:
        fichier.write(ENTETE_CACHE)
        yaml.safe_dump({theme: entrees for theme, entrees in cache.items() if entrees}, fichier, allow_unicode=True, sort_keys=True, width=120)


def regle_colonne(nom_colonne: str, nom_table: str = "") -> dict | None:
    """Règles (additive, precision) fournies par le module pour une colonne qu'il a créée."""
    return _REGLES.get((_theme(nom_table), _normaliser_simple(nom_colonne)))


def _memoriser_regle(theme: str, entete: str, entree: dict) -> None:
    regle = {cle: entree.get(cle) for cle in ("additive", "precision") if entree.get(cle) is not None}
    if regle:
        _REGLES[(theme, _normaliser_simple(entete))] = regle


# --------------------------------------------------------------------------- sans IA


def _correspondance_approchee(libelle: str, candidats: list[str]) -> tuple[str | None, float]:
    """Meilleur en-tête proche : mêmes nombres, mêmes mots sensibles, ressemblance ≥ seuil, sans ex aequo."""
    norme, nombres, sensibles = _signature(libelle)
    if not norme:
        return None, 0.0
    scores = []
    for candidat in candidats:
        norme_c, nombres_c, sensibles_c = _signature(candidat)
        if nombres_c != nombres or sensibles_c != sensibles:
            continue
        ratio = max(
            difflib.SequenceMatcher(None, norme, norme_c).ratio(),
            difflib.SequenceMatcher(None, " ".join(sorted(norme.split())), " ".join(sorted(norme_c.split()))).ratio(),
        )
        scores.append((ratio, candidat))
    scores.sort(reverse=True)
    if not scores or scores[0][0] < SEUIL_APPROCHE:
        return None, 0.0
    if len(scores) > 1 and scores[0][0] - scores[1][0] < ECART_AMBIGU:
        return None, 0.0
    return scores[0][1], round(scores[0][0], 2)


# --------------------------------------------------------------------------- IA

CONSIGNES_LLM = """Tu ranges des variables INSEE (données par IRIS, ville de Roubaix) dans un classeur Excel existant.
Pour chaque variable inconnue, dis si elle correspond à un en-tête existant de l'onglet (même notion,
même population, même tranche d'âge ; seul le libellé ou le code a changé). Sinon propose un nouvel en-tête.
Règles :
- "correspondance" : un en-tête EXACTEMENT copié de la liste fournie, ou null. La liste contient les noms
  du classeur validé : quand la notion est la même, reprends TOUJOURS l'en-tête existant, même formulé
  autrement (« Nombre de locataires » = « Rés princ occupées Locataires »). Dans le doute réel, null.
- "nouvel_entete" : seulement si aucun en-tête de la liste ne porte la même notion, libellé court en français dans le style des en-têtes existants
  (ex. « Pop 0-14 ans », « Rés princ 1 pièce », « Ménages au moins une voiture »).
- "additive" : true si c'est un effectif qui s'additionne entre IRIS (personnes, logements, ménages),
  false pour un taux, une part, une moyenne, une médiane, un quartile, un indice, un loyer, un montant moyen.
- "precision" : nombre de décimales, 0 pour un effectif, 1 pour un taux ou une part en %, 2 pour une densité, un indice ou un loyer.
- "confiance" : entre 0 et 1.
- "justification" : une phrase courte.
Codes INSEE (utile si le libellé manque) : P=population, H=hommes, F=femmes, ACT=actifs, ACTOCC=actifs occupés,
CHOM=chômeurs, ETUD=élèves/étudiants, SAL=salariés, NSCOL=non scolarisés, DIPLMIN=sans diplôme ou CEP,
CAPBEP=CAP-BEP, SUP2=bac+2, RP=résidences principales, ACH=achevées (période de construction), LOC=locataires,
PROP=propriétaires, MEN=ménages, FAM=familles ; 4 chiffres = tranche d'âge (2554 = 25-54 ans), P final = ou plus.
Réponds uniquement en JSON : {"colonnes": [{"code": ..., "correspondance": ..., "nouvel_entete": ...,
"additive": ..., "precision": ..., "confiance": ..., "justification": ...}]}"""


def _confiance_min() -> float:
    try:
        return float(os.getenv("BDDMAS_LLM_CONFIANCE_MIN", "0.8").replace(",", "."))
    except ValueError:
        return 0.8


def _extraire_json(texte: str) -> dict:
    texte = re.sub(r"^```(?:json)?|```$", "", texte.strip(), flags=re.MULTILINE).strip()
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin < debut:
        raise ValueError("aucun objet JSON dans la réponse")
    return json.loads(texte[debut:fin + 1])


def _exemples(serie) -> list:
    valeurs = serie.dropna().head(5).tolist()
    return [valeur.item() if hasattr(valeur, "item") else valeur for valeur in valeurs]


def _demander_llm(onglet: str, inconnues: list[dict], candidats: list[str]) -> dict[str, dict]:
    """Un appel par lot de variables ; renvoie {code: réponse brute}."""
    from .llm_wrapper import appeler_llm

    reponses = {}
    for debut in range(0, len(inconnues), TAILLE_LOT_LLM):
        lot = inconnues[debut:debut + TAILLE_LOT_LLM]
        prompt = (
            f"Onglet : {onglet}\n"
            f"En-têtes existants disponibles : {json.dumps(candidats, ensure_ascii=False)}\n"
            f"Variables inconnues : {json.dumps(lot, ensure_ascii=False, default=str)}"
        )
        numero = debut // TAILLE_LOT_LLM + 1
        total = (len(inconnues) - 1) // TAILLE_LOT_LLM + 1
        for essai in range(1, ESSAIS_LLM + 1):
            # Trace console : un appel peut prendre une minute (quota Groq), on montre qu'il avance
            print(f"  IA {onglet} : lot {numero}/{total} ({len(lot)} variables), essai {essai}…", flush=True)
            depart = time.monotonic()
            try:
                texte = appeler_llm(prompt, systeme=CONSIGNES_LLM, temperature=0, max_tokens=4000, format_json=True)
                elements = _extraire_json(texte).get("colonnes", [])
                print(f"  IA {onglet} : réponse en {time.monotonic() - depart:.0f} s", flush=True)
                break
            except (RuntimeError, ValueError) as exception:
                print(f"  IA {onglet} : échec après {time.monotonic() - depart:.0f} s ({exception})", flush=True)
                # Coupure réseau ou réponse illisible : nouvel essai après une pause
                if essai == ESSAIS_LLM:
                    raise
                time.sleep(20 * essai)
        for element in elements:
            if isinstance(element, dict) and element.get("code") is not None:
                reponses[str(element["code"])] = element
    return reponses


def _valider_reponse(reponse: dict, candidats: list[str]) -> dict:
    """Ne garde que des valeurs sûres : correspondance prise dans la liste, précision 0-2."""
    correspondance = reponse.get("correspondance")
    if correspondance is not None:
        # L'IA recopie parfois l'en-tête avec une petite variante (espace, point, casse)
        index = {_normaliser(candidat): candidat for candidat in candidats}
        texte = str(correspondance)
        correspondance = index.get(_normaliser(texte))
        if correspondance is None:
            _, nombres, sensibles = _signature(texte)
            compatibles = [cle for cle in index if _signature(cle)[1:] == (nombres, sensibles)]
            proches = difflib.get_close_matches(_normaliser(texte), compatibles, n=1, cutoff=0.9)
            correspondance = index[proches[0]] if proches else None
    nouvel_entete = reponse.get("nouvel_entete")
    nouvel_entete = re.sub(r"\s+", " ", str(nouvel_entete)).strip()[:120] if nouvel_entete else None
    if correspondance is None and nouvel_entete:
        # « Nouvel » en-tête identique à un en-tête existant : c'est une correspondance
        correspondance = {_normaliser(candidat): candidat for candidat in candidats}.get(_normaliser(nouvel_entete))
    try:
        confiance = min(max(float(str(reponse.get("confiance", 0)).replace(",", ".")), 0.0), 1.0)
    except (TypeError, ValueError):
        confiance = 0.0
    precision = reponse.get("precision")
    precision = precision if isinstance(precision, int) and not isinstance(precision, bool) and 0 <= precision <= 2 else None
    additive = reponse.get("additive") if isinstance(reponse.get("additive"), bool) else None
    return {
        "correspondance": correspondance,
        "nouvel_entete": nouvel_entete,
        "confiance": round(confiance, 2),
        "additive": additive,
        "precision": precision,
        "justification": str(reponse.get("justification") or "")[:300],
    }


# --------------------------------------------------------------------------- orchestration


def resoudre_colonnes(
    df,
    cle_onglet: str,
    codes_source: list[str],
    libelles_meta: dict,
    references: dict[str, list[str]],
    cache: dict,
):
    """Renomme les colonnes inconnues de l'onglet. Renvoie (df, décisions, cache_modifié)."""
    theme = _theme(cle_onglet)
    millesime = cle_onglet[len(theme):].strip() or None
    refs = references.get(theme, [])
    noms = list(df.columns)
    renommages: dict[str, str] = {}
    decisions: list[dict] = []
    cache_theme = cache.setdefault(theme, {})
    cache_modifie = False

    def decider(code, nom, entete, decision, methode, **details):
        if entete and entete != nom:
            renommages[nom] = entete
        decisions.append({
            "onglet": cle_onglet,
            "code": str(code),
            "libelle_source": nom,
            "entete": entete or nom,
            "decision": decision,
            "methode": methode,
            **details,
        })

    def entree_cache(code, nom, entete, decision, methode, confiance, **details):
        nonlocal cache_modifie
        cache_theme[_cle_variable(code, theme)] = {
            "libelle_source": nom,
            "entete": entete or nom,
            "decision": decision,
            "methode": methode,
            "confiance": confiance,
            "additive": details.get("additive"),
            "precision": details.get("precision"),
            "justification": details.get("justification", ""),
            "millesime": millesime,
            "date": date.today().isoformat(),
        }
        cache_modifie = True

    # 1. Exacte : nom identique, puis normalisé (casse, accents, « Population 0 à 14 ans »...)
    pris = {nom for nom in noms if nom in refs}
    index_refs = {}
    for ref in refs:
        index_refs.setdefault(_normaliser(ref), ref)
    a_traiter = []
    for code, nom in zip(codes_source, noms):
        if _est_technique(code, nom) or nom in refs:
            continue
        ref = index_refs.get(_normaliser(nom))
        if ref is not None and ref not in pris and ref not in noms:
            pris.add(ref)
            decider(code, nom, ref, "correspondance", "exacte", confiance=1.0)
        else:
            a_traiter.append((code, nom))

    # 2. Cache, puis correspondance approchée
    pour_llm = []
    for code, nom in a_traiter:
        entree = cache_theme.get(_cle_variable(code, theme))
        if entree and (entree.get("methode") == "manuel" or _normaliser(entree.get("libelle_source", "")) == _normaliser(nom)):
            entete = entree.get("entete") or nom
            if entete in pris or (entete in noms and entete != nom):
                entete = nom
            pris.add(entete)
            decider(code, nom, entete, entree.get("decision", "correspondance"), entree.get("methode", "manuel"),
                    confiance=entree.get("confiance"), justification=entree.get("justification", ""), depuis_cache=True)
            if entree.get("decision") != "correspondance":
                _memoriser_regle(theme, entete, entree)
            continue
        disponibles = [ref for ref in refs if ref not in pris and ref not in noms]
        ref, score = _correspondance_approchee(nom, disponibles)
        if ref:
            pris.add(ref)
            decider(code, nom, ref, "correspondance", "approchee", confiance=score)
            entree_cache(code, nom, ref, "correspondance", "approchee", score, justification="libellé proche (sans IA)")
            continue
        pour_llm.append((code, nom))

    # 3. IA pour le reste
    if pour_llm:
        from .llm_wrapper import llm_disponible

        disponibles = [ref for ref in refs if ref not in pris and ref not in noms]
        reponses, erreur = {}, None
        if llm_disponible():
            inconnues = [
                {
                    "code": str(code),
                    "libelle": libelles_meta.get(str(code).strip().casefold()) or nom,
                    "exemples": _exemples(df[nom]),
                }
                for code, nom in pour_llm
            ]
            try:
                reponses = _demander_llm(cle_onglet, inconnues, disponibles)
            except (RuntimeError, ValueError) as exception:
                erreur = str(exception)
        else:
            erreur = "IA non configurée (pas de clé dans .env)"

        seuil = _confiance_min()
        for code, nom in pour_llm:
            reponse = reponses.get(str(code))
            if reponse is None:
                decider(code, nom, nom, "non_resolue", "aucune", justification=erreur or "variable absente de la réponse IA")
                continue
            valide = _valider_reponse(reponse, disponibles)
            details = {cle: valide[cle] for cle in ("additive", "precision", "justification")}
            correspondance = valide["correspondance"]
            if correspondance in pris:
                correspondance = None
            libres = [ref for ref in disponibles if ref not in pris]
            if not correspondance and valide["nouvel_entete"]:
                # L'IA invente parfois une variante d'un en-tête existant (« Pop Ménages nb »)
                correspondance = _correspondance_approchee(valide["nouvel_entete"], libres)[0]
            # Sans libellé méta, l'IA ne voit que le code : plus d'exigence, et pas de nouveau nom inventé
            sans_libelle = (
                str(code).strip().casefold() not in libelles_meta
                and str(code).casefold().endswith(str(nom).casefold())
            )
            seuil_variable = max(seuil, CONFIANCE_SANS_LIBELLE) if sans_libelle else seuil
            if valide["confiance"] < seuil_variable or (sans_libelle and not correspondance):
                entete, decision = nom, "non_resolue"
            elif correspondance:
                entete, decision = correspondance, "correspondance"
            else:
                entete, decision = valide["nouvel_entete"] or nom, "nouvelle"
                if entete in pris or (entete in noms and entete != nom):
                    entete = nom
            pris.add(entete)
            decider(code, nom, entete, decision, "llm", confiance=valide["confiance"], **details)
            entree_cache(code, nom, entete, decision, "llm", valide["confiance"], **details)
            if decision != "correspondance":
                _memoriser_regle(theme, entete, details)

    if renommages:
        df = df.rename(columns=renommages)
    return df, decisions, cache_modifie


def resumer_decisions(decisions: list[dict]) -> list[dict]:
    """Avertissements de pré-contrôle : une ligne par onglet, seulement ce qui mérite une relecture."""
    avertissements = []
    par_onglet: dict[str, list[dict]] = {}
    for decision in decisions:
        if decision["methode"] != "exacte":
            par_onglet.setdefault(decision["onglet"], []).append(decision)
    for onglet, liste in par_onglet.items():
        rattachees = [d for d in liste if d["decision"] == "correspondance"]
        nouvelles = [d for d in liste if d["decision"] == "nouvelle"]
        non_resolues = [d for d in liste if d["decision"] == "non_resolue"]
        morceaux = []
        if rattachees:
            morceaux.append(f"{len(rattachees)} rattachée(s) : " + ", ".join(
                f"{d['libelle_source']} → {d['entete']}" for d in rattachees))
        if nouvelles:
            morceaux.append(f"{len(nouvelles)} nouvelle(s) : " + ", ".join(
                f"{d['libelle_source']} → {d['entete']}" for d in nouvelles))
        if non_resolues:
            morceaux.append(f"{len(non_resolues)} non résolue(s), gardée(s) sous leur nom : " + ", ".join(
                d["libelle_source"] for d in non_resolues))
        avertissements.append({
            "code": "colonnes_auto",
            "theme": onglet,
            "decisions": liste,
            "message": f"Colonnes inconnues du modèle ({NOM_CACHE}). " + " ; ".join(morceaux) + ".",
        })
    return avertissements
