"""Background video jobs for Kiara Chat: write the script, narrate, render. One job at a time."""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import threading
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import uuid4

from app.video_studio.engine import LIBRARY_SHOTS, QUALITIES, VideoError, narrate, render
from app.video_studio.writer import build_prompt, parse_script

Generate = Callable[[str], Awaitable[str]]
JOB_ID = re.compile(r"[0-9a-f]{32}")


class VideoJobs:
    def __init__(self, root: Path, generate: Generate, *, workers: int = 0) -> None:
        self.root = root
        self.generate = generate
        self.workers = workers
        self.jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _public(self, job: dict) -> dict:
        return {key: job[key] for key in ("id", "status", "stage", "progress", "message", "title", "duration", "warnings", "error", "created_at")}

    def _owned(self, owner: str, job_id: object) -> dict:
        if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
            raise VideoError("Tarefa de vídeo inválida.")
        job = self.jobs.get(job_id)
        if job is None or job["owner"] != owner:
            raise VideoError("Tarefa de vídeo não encontrada.")
        return job

    def start(self, owner: str, brief: str, audience: list[str], quality: str = "1080p") -> dict:
        if quality not in QUALITIES:
            raise VideoError("Qualidade deve ser 1080p ou 720p.")
        with self._lock:
            if any(job["status"] in {"queued", "running"} for job in self.jobs.values()):
                raise VideoError("Já existe um vídeo em produção. Aguarde ele terminar.")
            job_id = uuid4().hex
            job = {"id": job_id, "owner": owner, "status": "running", "stage": "script", "progress": 0.0,
                   "message": "Escrevendo o roteiro", "title": brief[:80], "duration": None, "warnings": [],
                   "error": None, "created_at": time.time(), "path": None}
            self.jobs[job_id] = job
        threading.Thread(target=self._run, args=(job, brief, audience, quality), daemon=True).start()
        return self._public(job)

    def status(self, owner: str, job_id: object) -> dict:
        return self._public(self._owned(owner, job_id))

    def video(self, owner: str, job_id: object) -> Path:
        job = self._owned(owner, job_id)
        if job["status"] != "done" or not job["path"]:
            raise VideoError("O vídeo ainda não está pronto.")
        return Path(job["path"])

    def _update(self, job: dict, stage: str, value: float, message: str) -> None:
        weights = {"script": (0, .05), "narration": (.05, .15), "render": (.15, .97), "encode": (.97, 1)}
        low, high = weights.get(stage, (0, 1))
        job.update(stage=stage, progress=round(low + (high - low) * min(1, max(0, value)), 3), message=message)

    def _run(self, job: dict, brief: str, audience: list[str], quality: str) -> None:
        project = self.root / job["id"]
        try:
            project.mkdir(parents=True)
            raw = asyncio.run(self.generate(build_prompt(brief, audience)))
            script = parse_script(raw, audience)
            (project / "shots").mkdir()
            for scene in script["scenes"]:
                for shot in scene.get("shots", []):
                    shutil.copyfile(LIBRARY_SHOTS / f"{shot['shot']}.png", project / "shots" / f"{shot['shot']}.png")
            (project / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
            timeline = narrate(project, progress=lambda s, v, m: self._update(job, s, v, m))
            job.update(duration=timeline["duration"], warnings=timeline["warnings"][:10])
            output = render(project, quality=quality, workers=self.workers, progress=lambda s, v, m: self._update(job, s, v, m))
            job.update(status="done", stage="done", progress=1.0, message="Vídeo pronto", path=str(output))
        except VideoError as error:
            job.update(status="failed", error=str(error), message="Não foi possível gerar o vídeo")
        except Exception:  # noqa: BLE001 - job boundary: never leak internals to the browser
            job.update(status="failed", error="Falha inesperada ao gerar o vídeo. Verifique ffmpeg, Playwright e a conexão.",
                       message="Não foi possível gerar o vídeo")
