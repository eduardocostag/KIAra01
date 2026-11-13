"""Background video jobs for Kiara Chat: write the script, narrate, render. One job at a time."""
from __future__ import annotations

import asyncio
import json
import math
import os
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
        self._lock = threading.RLock()
        self._last_save: dict[str, float] = {}
        if root.is_symlink():
            raise VideoError("Diretório de vídeos inválido.")
        self.root.mkdir(parents=True, exist_ok=True)
        self.root = self.root.resolve()
        self._recover()

    def _project(self, job_id: str) -> Path:
        project = self.root / job_id
        if not JOB_ID.fullmatch(job_id) or project.is_symlink() or project.resolve().parent != self.root:
            raise VideoError("Diretório de vídeo inválido.")
        return project

    def _output(self, job_id: str) -> Path:
        project = self._project(job_id)
        output = project / "out" / "video.mp4"
        if output.parent.is_symlink() or output.is_symlink() or output.resolve().parent != project / "out":
            raise VideoError("Arquivo de vídeo inválido.")
        return output

    def _persist(self, job: dict) -> None:
        project = self._project(job["id"])
        target = project / "job.json"
        if target.is_symlink():
            raise VideoError("Manifesto de vídeo inválido.")
        temporary = project / f".job-{uuid4().hex}.tmp"
        data = {"version": 1, "owner": job["owner"], **self._public(job)}
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            self._last_save[job["id"]] = time.monotonic()
        finally:
            temporary.unlink(missing_ok=True)

    def _recover(self) -> None:
        for project in self.root.iterdir():
            if not JOB_ID.fullmatch(project.name) or project.is_symlink() or not project.is_dir():
                continue
            manifest = project / "job.json"
            try:
                if manifest.is_symlink() or manifest.stat().st_size > 64000:
                    continue
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1 or data.get("id") != project.name or "path" in data:
                    continue
                if not isinstance(data.get("owner"), str) or not 1 <= len(data["owner"].strip()) <= 500:
                    continue
                if data.get("status") not in {"queued", "running", "done", "failed"}:
                    continue
                if any(not isinstance(data.get(key), str) or len(data[key]) > limit
                       for key, limit in (("title", 80), ("stage", 100), ("message", 4000))):
                    continue
                if any(not isinstance(data.get(key), (int, float)) or isinstance(data[key], bool)
                       or not math.isfinite(data[key]) or data[key] < 0 for key in ("progress", "created_at")):
                    continue
                if data["progress"] > 1 or (data.get("duration") is not None and (
                        not isinstance(data["duration"], (int, float)) or isinstance(data["duration"], bool)
                        or not math.isfinite(data["duration"]) or data["duration"] < 0)):
                    continue
                if (not isinstance(data.get("warnings"), list) or len(data["warnings"]) > 10
                        or any(not isinstance(item, str) or len(item) > 4000 for item in data["warnings"])
                        or data.get("error") is not None and (not isinstance(data["error"], str) or len(data["error"]) > 4000)):
                    continue
                job = {key: data[key] for key in ("id", "owner", "status", "stage", "progress", "message", "title", "duration", "warnings", "error", "created_at")}
                job["path"] = None
                if job["status"] in {"queued", "running"}:
                    job.update(status="failed", error="A ponte foi reiniciada durante a geração. Inicie um novo vídeo para tentar novamente.",
                               message="Geração interrompida pelo reinício da ponte")
                elif job["status"] == "done":
                    output = self._output(job["id"])
                    if output.is_file():
                        job["path"] = str(output)
                    else:
                        job.update(status="failed", error="O arquivo deste vídeo não está disponível.", message="Vídeo indisponível")
                self.jobs[job["id"]] = job
                self._persist(job)
            except (OSError, ValueError, TypeError, KeyError, VideoError):
                # A corrupt or unsafe manifest must never grant ownership or
                # prevent other valid videos from being restored.
                self.jobs.pop(project.name, None)

    def _public(self, job: dict) -> dict:
        result = {key: job[key] for key in ("id", "status", "stage", "progress", "message", "title", "duration", "warnings", "error", "created_at")}
        result["warnings"] = list(result["warnings"])
        return result

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
        if not isinstance(owner, str) or not 1 <= len(owner.strip()) <= 500:
            raise VideoError("Proprietário de vídeo inválido.")
        with self._lock:
            if any(job["status"] in {"queued", "running"} for job in self.jobs.values()):
                raise VideoError("Já existe um vídeo em produção. Aguarde ele terminar.")
            job_id = uuid4().hex
            job = {"id": job_id, "owner": owner, "status": "running", "stage": "script", "progress": 0.0,
                   "message": "Escrevendo o roteiro", "title": brief[:80], "duration": None, "warnings": [],
                   "error": None, "created_at": time.time(), "path": None}
            self._project(job_id).mkdir()
            self._persist(job)
            self.jobs[job_id] = job
            initial = self._public(job)
        threading.Thread(target=self._run, args=(job, brief, audience, quality), daemon=True).start()
        return initial

    def status(self, owner: str, job_id: object) -> dict:
        with self._lock:
            return self._public(self._owned(owner, job_id))

    def video(self, owner: str, job_id: object) -> Path:
        with self._lock:
            job = self._owned(owner, job_id)
            if job["status"] != "done" or not job["path"]:
                raise VideoError("O vídeo ainda não está pronto.")
            output = self._output(job["id"])
            if not output.is_file():
                raise VideoError("O arquivo deste vídeo não está disponível.")
            return output

    def _update(self, job: dict, stage: str, value: float, message: str) -> None:
        weights = {"script": (0, .05), "narration": (.05, .15), "render": (.15, .97), "encode": (.97, 1)}
        low, high = weights.get(stage, (0, 1))
        with self._lock:
            changed_stage = job["stage"] != stage
            job.update(stage=stage, progress=round(low + (high - low) * min(1, max(0, value)), 3), message=message)
            if changed_stage or time.monotonic() - self._last_save.get(job["id"], 0) >= 1:
                self._persist(job)

    def _change(self, job: dict, **values) -> None:
        with self._lock:
            job.update(values)
            self._persist(job)

    def _run(self, job: dict, brief: str, audience: list[str], quality: str) -> None:
        try:
            project = self._project(job["id"])
            raw = asyncio.run(self.generate(build_prompt(brief, audience)))
            script = parse_script(raw, audience)
            (project / "shots").mkdir()
            for scene in script["scenes"]:
                for shot in scene.get("shots", []):
                    shutil.copyfile(LIBRARY_SHOTS / f"{shot['shot']}.png", project / "shots" / f"{shot['shot']}.png")
            (project / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
            timeline = narrate(project, progress=lambda s, v, m: self._update(job, s, v, m))
            self._change(job, duration=timeline["duration"], warnings=timeline["warnings"][:10])
            output = render(project, quality=quality, workers=self.workers, progress=lambda s, v, m: self._update(job, s, v, m))
            if output.resolve() != self._output(job["id"]) or not self._output(job["id"]).is_file():
                raise VideoError("Arquivo de vídeo inválido.")
            self._change(job, status="done", stage="done", progress=1.0, message="Vídeo pronto", path=str(output))
        except VideoError as error:
            self._change(job, status="failed", error=str(error), message="Não foi possível gerar o vídeo")
        except Exception:  # noqa: BLE001 - job boundary: never leak internals to the browser
            self._change(job, status="failed", error="Falha inesperada ao gerar o vídeo. Verifique ffmpeg, Playwright e a conexão.",
                       message="Não foi possível gerar o vídeo")
