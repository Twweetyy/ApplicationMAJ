import os
import shutil
import tempfile
import threading
import time
import uuid
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from main_bddmas import DOSSIER_DICOS, FICHIER_MODELE, ErreurPrecontrole, executer_pipeline
from modules.ingestion import analyser_fichiers_entree


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
_VERROU_JOBS = threading.RLock()


def _nettoyer_anciens_jobs() -> None:
    limite = time.time() - DUREE_CONSERVATION_SECONDES
    with _VERROU_JOBS:
        anciens = [
            job_id
            for job_id, job in _JOBS.items()
            if job["created_at"] < limite and job["status"] not in {"queued", "processing"}
        ]
        for job_id in anciens:
            job = _JOBS.pop(job_id)
            shutil.rmtree(job["root"], ignore_errors=True)

    for dossier in DOSSIER_JOBS.iterdir():
        if dossier.is_dir() and dossier.stat().st_mtime < limite:
            shutil.rmtree(dossier, ignore_errors=True)


def _nom_fichier_securise(nom: str | None) -> str:
    if not nom:
        raise HTTPException(status_code=400, detail="Un fichier envoyé n’a pas de nom.")
    nom = nom.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if nom in {"", ".", ".."} or not nom.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail=f"Format non pris en charge : {nom or 'fichier sans nom'}")
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
            )
        avertissements = [
            ligne.strip()
            for ligne in sortie_console.getvalue().splitlines()
            if ligne.strip().startswith("Erreur lors du calcul de")
        ]
        with _VERROU_JOBS:
            job["classeur"] = resultat["classeur"]
            job["themes"] = resultat["themes"]
            job["avertissements_calcul"] = avertissements
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
        if any(item["status"] in {"queued", "processing"} for item in _JOBS.values()):
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
