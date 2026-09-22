"""CinetixOS 503 — API local (FastAPI) para subir cortos y subtitularlos.

Puerto 5030. Sin nube: todo el procesado ocurre en la maquina.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import pipeline  # noqa: E402

UPLOADS = ROOT / "uploads"
DATA = ROOT / "data"
FRONTEND = ROOT / "frontend"
UPLOADS.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)

app = FastAPI(title="CinetixOS 503 Subtitulos", version="1.0.0")

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}


class ProcessRequest(BaseModel):
    target: str = "es"
    whisper_model: str | None = None
    translate_model: str | None = None
    remove_burned: str = "auto"
    strip_soft: bool = True
    force: bool = False


def _set(job_id: str, **fields) -> None:
    with LOCK:
        JOBS.setdefault(job_id, {})
        JOBS[job_id].update(fields)


def _run_job(job_id: str, path: str, options: pipeline.ProcessOptions) -> None:
    def progress(msg: str, pct: float) -> None:
        _set(job_id, step=msg, progress=round(pct, 3), updated=time.time())

    _set(job_id, status="running", step="Iniciando...", progress=0.0)
    try:
        options.output_dir = str(DATA / job_id)
        report = pipeline.process(path, options, progress)
        _set(
            job_id,
            status="done",
            progress=1.0,
            report=report.as_dict(),
            updated=time.time(),
        )
    except Exception as exc:  # noqa: BLE001
        _set(job_id, status="error", error=str(exc), updated=time.time())


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in VIDEO_EXT:
        raise HTTPException(400, f"Extension no soportada: {ext}")
    job_id = uuid.uuid4().hex[:12]
    dest = UPLOADS / f"{job_id}{ext}"
    with open(dest, "wb") as fh:
        while chunk := await file.read(1 << 20):
            fh.write(chunk)
    _set(
        job_id,
        id=job_id,
        filename=file.filename,
        path=str(dest),
        status="uploaded",
        progress=0.0,
        created=time.time(),
        updated=time.time(),
    )
    return {"job_id": job_id, "filename": file.filename}


@app.post("/api/process/{job_id}")
def start(job_id: str, req: ProcessRequest):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job no encontrado")
    if job.get("status") == "running":
        raise HTTPException(409, "job ya en ejecucion")
    options = pipeline.ProcessOptions(
        target_lang=req.target,
        whisper_model=req.whisper_model,
        translate_model=req.translate_model,
        remove_burned=req.remove_burned,
        strip_soft=req.strip_soft,
        force=req.force,
    )
    threading.Thread(target=_run_job, args=(job_id, job["path"], options), daemon=True).start()
    return {"job_id": job_id, "status": "running"}


@app.get("/api/jobs")
def list_jobs():
    return {"jobs": sorted(JOBS.values(), key=lambda j: j.get("created", 0), reverse=True)}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job no encontrado")
    return job


@app.get("/api/download/{job_id}/{kind}")
def download(job_id: str, kind: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job no encontrado")
    report = job.get("report") or {}
    path = report.get("srt") if kind == "srt" else report.get("final")
    if not path or not os.path.exists(path):
        raise HTTPException(404, "archivo no disponible")
    return FileResponse(path, filename=os.path.basename(path))


@app.get("/", response_class=HTMLResponse)
def index():
    return (FRONTEND / "index.html").read_text(encoding="utf-8")


if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
