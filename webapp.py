import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from main_bddmas import DOSSIER_DICOS, FICHIER_MODELE, ErreurPrecontrole, executer_pipeline
from modules.bpe import PERIMETRES as PERIMETRES_BPE, ErreurBPE, generer_classeur_bpe
from modules.ingestion import analyser_fichiers_entree
from modules.lecture import EXTENSIONS_DONNEES


DOSSIER_APPLICATION = Path(__file__).resolve().parent
DOSSIER_WEB = DOSSIER_APPLICATION / "web"
DOSSIER_JOBS = Path(os.environ.get("BDDMAS_WEB_JOB_ROOT", Path(tempfile.gettempdir()) / "bddmas-web-jobs"))
DUREE_CONSERVATION_SECONDES = 12 * 60 * 60
TAILLE_BLOC_COPIE = 1024 * 1024
NOMBRE_MAX_FICHIERS = 60

DOSSIER_JOBS.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="BDDMAS | Génération de classeur", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=DOSSIER_WEB), name="static")

_JOBS: dict[str, dict] = {}
# Classeurs BPE (page /bpe), indépendants des lots BDDMAS
_JOBS_BPE: dict[str, dict] = {}
_VERROU_JOBS = threading.RLock()


def _nettoyer_anciens_jobs() -> None:
    limite = time.time() - DUREE_CONSERVATION_SECONDES
    with _VERROU_JOBS:
        for jobs in (_JOBS, _JOBS_BPE):
            anciens = [
                job_id
                for job_id, job in jobs.items()
                if job["created_at"] < limite and job["status"] not in {"queued", "processing"}
            ]
            for job_id in anciens:
                job = jobs.pop(job_id)
                shutil.rmtree(job["root"], ignore_errors=True)

    for dossier in DOSSIER_JOBS.iterdir():
        if dossier.is_dir() and dossier.stat().st_mtime < limite:
            shutil.rmtree(dossier, ignore_errors=True)


_INDICATEUR_NON_CALCULE = re.compile(r"Indicateur non calculé '(.+)' : variable absente de ce millésime \((.+)\)$")


def _nom_fichier_securise(nom: str | None) -> str:
    if not nom:
        raise HTTPException(status_code=400, detail="Un fichier envoyé n’a pas de nom.")
    nom = nom.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if nom in {"", ".", ".."} or not nom.lower().endswith(EXTENSIONS_DONNEES):
        raise HTTPException(status_code=400, detail=f"Format non pris en charge : {nom or 'fichier sans nom'}")
    if _est_metadonnee(nom) and not nom.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail=f"Les métadonnées doivent être au format CSV : {nom}")
    return nom


def _est_metadonnee(nom: str) -> bool:
    nom_normalise = nom.casefold()
    return nom_normalise.startswith("meta_") or nom_normalise.startswith("varmod_")


def _copier_televersement(fichier: UploadFile, destination: Path) -> None:
    with destination.open("wb") as sortie:
        shutil.copyfileobj(fichier.file, sortie, length=TAILLE_BLOC_COPIE)


def _job_public(job: dict) -> dict:
    return {
        "id": job["id"],
        "status": job["status"],
        "rapport": job["rapport"],
        "fichiers": job["fichiers"],
        "avertissements_calcul": job.get("avertissements_calcul", []),
        "indicateurs_non_calcules": job.get("indicateurs_non_calcules", []),
        # Colonnes inconnues traitées par modules/colonnes_auto.py (sauf correspondances exactes)
        "colonnes_auto": [
            decision for decision in job.get("colonnes_auto", []) if decision.get("methode") != "exacte"
        ],
        "erreur": job.get("erreur"),
        "classeur_disponible": bool(job.get("classeur") and Path(job["classeur"]).is_file()),
    }


def _obtenir_job(job_id: str) -> dict:
    with _VERROU_JOBS:
        job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Lot introuvable ou expiré.")
    return job


def _generer_classeur(job_id: str) -> None:
    with _VERROU_JOBS:
        job = _JOBS.get(job_id)
        if job is None:
            return
        job["status"] = "processing"

    chemin_sortie = Path(job["root"]) / "TAB_BDDMAS_Tout_perimetre.xlsx"
    try:
        sortie_console = StringIO()
        with redirect_stdout(sortie_console):
            resultat = executer_pipeline(
                dossier_data=job["data"],
                dossier_dicos=job["dicos"],
                chemin_sortie=str(chemin_sortie),
                chemin_modele=str(FICHIER_MODELE),
                dossier_export_sig=None,
                persister_sql=False,
                afficher_progression=False,
                afficher_messages=False,
                # Copie du lot sans méta : millésimes validés, vocabulaire et cache lus dans le vrai dépôt
                dossier_dicos_reference=str(DOSSIER_DICOS),
            )
        lignes = [ligne.strip() for ligne in sortie_console.getvalue().splitlines()]
        avertissements = [ligne for ligne in lignes if ligne.startswith("Erreur lors du calcul de")]
        # Variables absentes du millésime : information, pas une erreur (indicateur laissé vide)
        non_calcules = [
            {"indicateur": trouve.group(1), "variable": trouve.group(2)}
            for trouve in map(_INDICATEUR_NON_CALCULE.match, lignes)
            if trouve
        ]
        with _VERROU_JOBS:
            job["classeur"] = resultat["classeur"]
            job["themes"] = resultat["themes"]
            job["avertissements_calcul"] = avertissements
            job["indicateurs_non_calcules"] = non_calcules
            job["colonnes_auto"] = resultat.get("colonnes_auto", [])
            job["status"] = "done_with_warnings" if avertissements else "done"
    except ErreurPrecontrole as erreur:
        with _VERROU_JOBS:
            job["rapport"] = erreur.rapport
            job["status"] = "invalid"
    except Exception as erreur:
        with _VERROU_JOBS:
            job["erreur"] = f"{type(erreur).__name__}: {erreur}"
            job["status"] = "failed"


@app.get("/")
def accueil():
    return FileResponse(DOSSIER_WEB / "index.html")


@app.get("/bpe")
def page_bpe():
    return FileResponse(DOSSIER_WEB / "bpe.html")


@app.get("/api/health")
def etat_service():
    return {"status": "ok"}


@app.post("/api/jobs", status_code=201)
def creer_job(files: list[UploadFile] = File(...)):
    _nettoyer_anciens_jobs()
    if len(files) > NOMBRE_MAX_FICHIERS:
        raise HTTPException(status_code=413, detail=f"Maximum {NOMBRE_MAX_FICHIERS} fichiers par lot.")

    job_id = uuid.uuid4().hex
    racine = DOSSIER_JOBS / job_id
    data_dir = racine / "data"
    dicos_dir = racine / "dictionnaires"
    meta_dir = dicos_dir / "meta"
    data_dir.mkdir(parents=True)
    shutil.copytree(
        DOSSIER_DICOS,
        dicos_dir,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("meta", "__pycache__"),
    )
    meta_dir.mkdir(parents=True, exist_ok=True)

    fichiers_recus = []
    noms_deja_vus = set()
    try:
        for fichier in files:
            nom = _nom_fichier_securise(fichier.filename)
            cle_nom = nom.casefold()
            if cle_nom in noms_deja_vus:
                raise HTTPException(status_code=400, detail=f"Nom de fichier envoyé plusieurs fois : {nom}")
            noms_deja_vus.add(cle_nom)

            est_meta = _est_metadonnee(nom)
            destination_dir = meta_dir if est_meta else data_dir
            destination = destination_dir / nom
            _copier_televersement(fichier, destination)
            fichiers_recus.append({"nom": nom, "type": "métadonnée" if est_meta else "donnée"})

        rapport = analyser_fichiers_entree(str(data_dir), str(dicos_dir))
        status = "invalid" if rapport["erreurs"] else "ready"
        job = {
            "id": job_id,
            "root": str(racine),
            "data": str(data_dir),
            "dicos": str(dicos_dir),
            "created_at": time.time(),
            "status": status,
            "rapport": rapport,
            "fichiers": fichiers_recus,
            "erreur": None,
            "avertissements_calcul": [],
            "classeur": None,
        }
        with _VERROU_JOBS:
            _JOBS[job_id] = job
        return _job_public(job)
    except HTTPException:
        shutil.rmtree(racine, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(racine, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse du lot : {type(exc).__name__}: {exc}")


@app.get("/api/jobs/{job_id}")
def consulter_job(job_id: str):
    return _job_public(_obtenir_job(job_id))


@app.post("/api/jobs/{job_id}/generate", status_code=202)
def lancer_generation(job_id: str, background_tasks: BackgroundTasks):
    job = _obtenir_job(job_id)
    with _VERROU_JOBS:
        if job["status"] != "ready":
            raise HTTPException(status_code=409, detail="Ce lot n’est pas prêt à être généré.")
        if any(item["status"] in {"queued", "processing"} for item in [*_JOBS.values(), *_JOBS_BPE.values()]):
            raise HTTPException(status_code=409, detail="Une génération est déjà en cours sur ce serveur.")
        job["status"] = "queued"
    background_tasks.add_task(_generer_classeur, job_id)
    return _job_public(job)


@app.get("/api/jobs/{job_id}/download")
def telecharger_classeur(job_id: str):
    job = _obtenir_job(job_id)
    chemin = job.get("classeur")
    if job["status"] not in {"done", "done_with_warnings"} or not chemin or not Path(chemin).is_file():
        raise HTTPException(status_code=409, detail="Le classeur n’est pas encore disponible.")
    return FileResponse(
        chemin,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="TAB_BDDMAS_Tout_perimetre.xlsx",
    )


@app.delete("/api/jobs/{job_id}", status_code=204)
def supprimer_job(job_id: str):
    job = _obtenir_job(job_id)
    if job["status"] in {"queued", "processing"}:
        raise HTTPException(status_code=409, detail="Impossible de supprimer un lot en cours de génération.")
    with _VERROU_JOBS:
        _JOBS.pop(job_id, None)
    shutil.rmtree(job["root"], ignore_errors=True)
    return None


# --------------------------------------------------------------------------- BPE (Base permanente des équipements)


def _job_bpe_public(job: dict) -> dict:
    return {
        "id": job["id"],
        "status": job["status"],
        "perimetre": PERIMETRES_BPE[job["perimetre"]],
        "fichiers": job["fichiers"],
        "resume": job.get("resume"),
        "erreur": job.get("erreur"),
    }


def _obtenir_job_bpe(job_id: str) -> dict:
    with _VERROU_JOBS:
        job = _JOBS_BPE.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Traitement BPE introuvable ou expiré.")
    return job


def _generer_classeur_bpe(job_id: str) -> None:
    with _VERROU_JOBS:
        job = _JOBS_BPE.get(job_id)
        if job is None:
            return
        job["status"] = "processing"
    try:
        resume = generer_classeur_bpe(
            chemin_bpe=job["source"],
            chemin_sortie=str(Path(job["root"]) / "BPE_equipements.xlsx"),
            perimetre=job["perimetre"],
            chemin_varmod=job["varmod"],
            dossier_dicos=str(DOSSIER_DICOS),
        )
        with _VERROU_JOBS:
            job["resume"] = resume
            job["status"] = "done"
    except ErreurBPE as erreur:
        with _VERROU_JOBS:
            job["erreur"] = str(erreur)
            job["status"] = "failed"
    except Exception as erreur:
        with _VERROU_JOBS:
            job["erreur"] = f"{type(erreur).__name__}: {erreur}"
            job["status"] = "failed"


@app.post("/api/bpe/jobs", status_code=202)
def creer_job_bpe(
    background_tasks: BackgroundTasks,
    source: UploadFile = File(...),
    varmod: UploadFile | None = File(None),
    perimetre: str = Form("roubaix"),
):
    """Reçoit le fichier BPE (et éventuellement le varmod), puis lance la génération du classeur."""
    _nettoyer_anciens_jobs()
    if perimetre not in PERIMETRES_BPE:
        raise HTTPException(status_code=400, detail=f"Périmètre inconnu : {perimetre}")
    nom_source = _nom_fichier_securise(source.filename)
    nom_varmod = None
    if varmod is not None and varmod.filename:
        nom_varmod = varmod.filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not nom_varmod.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail=f"Le varmod doit être au format CSV : {nom_varmod}")

    with _VERROU_JOBS:
        if any(item["status"] in {"queued", "processing"} for item in [*_JOBS.values(), *_JOBS_BPE.values()]):
            raise HTTPException(status_code=409, detail="Un traitement est déjà en cours sur ce serveur.")

    job_id = uuid.uuid4().hex
    racine = DOSSIER_JOBS / f"bpe-{job_id}"
    racine.mkdir(parents=True)
    try:
        chemin_source = racine / nom_source
        _copier_televersement(source, chemin_source)
        chemin_varmod = None
        if nom_varmod:
            chemin_varmod = racine / f"varmod_{nom_varmod}"
            _copier_televersement(varmod, chemin_varmod)
    except Exception as exc:
        shutil.rmtree(racine, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la réception : {type(exc).__name__}: {exc}")

    job = {
        "id": job_id,
        "root": str(racine),
        "source": str(chemin_source),
        "varmod": str(chemin_varmod) if chemin_varmod else None,
        "perimetre": perimetre,
        "created_at": time.time(),
        "status": "queued",
        "fichiers": [nom for nom in (nom_source, nom_varmod) if nom],
        "resume": None,
        "erreur": None,
    }
    with _VERROU_JOBS:
        _JOBS_BPE[job_id] = job
    background_tasks.add_task(_generer_classeur_bpe, job_id)
    return _job_bpe_public(job)


@app.get("/api/bpe/jobs/{job_id}")
def consulter_job_bpe(job_id: str):
    return _job_bpe_public(_obtenir_job_bpe(job_id))


@app.get("/api/bpe/jobs/{job_id}/download")
def telecharger_classeur_bpe(job_id: str):
    job = _obtenir_job_bpe(job_id)
    resume = job.get("resume") or {}
    chemin = resume.get("classeur")
    if job["status"] != "done" or not chemin or not Path(chemin).is_file():
        raise HTTPException(status_code=409, detail="Le classeur BPE n’est pas encore disponible.")
    return FileResponse(
        chemin,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=resume["nom_fichier"],
    )


@app.delete("/api/bpe/jobs/{job_id}", status_code=204)
def supprimer_job_bpe(job_id: str):
    job = _obtenir_job_bpe(job_id)
    if job["status"] in {"queued", "processing"}:
        raise HTTPException(status_code=409, detail="Impossible de supprimer un traitement en cours.")
    with _VERROU_JOBS:
        _JOBS_BPE.pop(job_id, None)
    shutil.rmtree(job["root"], ignore_errors=True)
    return None
