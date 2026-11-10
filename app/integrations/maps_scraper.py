"""Bounded local CLI adapter for gosom/google-maps-scraper (MIT)."""
from __future__ import annotations

import asyncio
import csv
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from app.security.kill_switch import KillSwitch


class MapsScraperError(RuntimeError):
    pass


def validate_search(query: str, limit: int) -> None:
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 300:
        raise ValueError("A consulta deve ter entre 1 e 300 caracteres.")
    if any(ord(char) < 32 for char in query):
        raise ValueError("A consulta deve ocupar uma única linha sem caracteres de controle.")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("O limite deve estar entre 1 e 50.")


def _public_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username:
            return value[:2048]
    except ValueError:
        pass
    return ""


class MapsScraperClient:
    """One query per process, no shell, conservative depth/concurrency, local output."""

    def __init__(
        self, executable: str | Path, output_root: Path, kill_switch: KillSwitch,
        timeout: int = 600,
    ) -> None:
        candidate = Path(executable).expanduser()
        if not candidate.is_absolute() or not candidate.is_file():
            raise ValueError("Informe o caminho absoluto do executável Google Maps Scraper.")
        if os.name == "nt" and candidate.suffix.lower() != ".exe":
            raise ValueError("O Google Maps Scraper deve ser um executável .exe no Windows.")
        if type(timeout) is not int or not 30 <= timeout <= 1800:
            raise ValueError("O timeout do scraper deve estar entre 30 e 1800 segundos.")
        self.executable = candidate.resolve()
        self.output_root = Path(output_root).resolve()
        self.kill_switch = kill_switch
        self.timeout = timeout
        self._lock = asyncio.Lock()

    async def search(self, *, query: str, limit: int) -> list[dict[str, Any]]:
        validate_search(query, limit)
        async with self._lock:
            return await asyncio.to_thread(self._run, query.strip(), limit)

    def _run(self, query: str, limit: int) -> list[dict[str, Any]]:
        if self.kill_switch.stopped:
            raise MapsScraperError("Kill switch ativo.")
        folder = self.output_root / uuid4().hex
        folder.mkdir(parents=True, exist_ok=False)
        input_file, results_file = folder / "queries.txt", folder / "results.csv"
        input_file.write_text(query + "\n", encoding="utf-8")
        command = [
            str(self.executable), "-input", str(input_file), "-results", str(results_file),
            "-depth", "1", "-c", "1", "-lang", "pt", "-exit-on-inactivity", "3m",
        ]
        env = dict(os.environ, DISABLE_TELEMETRY="1")
        # Keep the Go Playwright runtime beside this local installation instead
        # of requiring write access to the Windows user profile.
        env.setdefault("PLAYWRIGHT_DRIVER_PATH", str(self.executable.parent / "driver"))
        env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(self.executable.parent / "browsers"))
        try:
            process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, cwd=folder, env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            raise MapsScraperError("Não foi possível iniciar o Google Maps Scraper.") from exc
        self.kill_switch.register(process)
        try:
            process.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired as exc:
            self.kill_switch._kill_tree(process.pid)
            process.wait()
            raise MapsScraperError(
                "Google Maps Scraper excedeu o tempo limite; saída parcial preservada localmente."
            ) from exc
        finally:
            self.kill_switch.unregister(process)
        if self.kill_switch.stopped:
            raise MapsScraperError("Pesquisa interrompida pelo kill switch.")
        if process.returncode != 0:
            raise MapsScraperError("Google Maps Scraper falhou; nenhuma ficha foi importada.")
        if not results_file.is_file():
            raise MapsScraperError("Google Maps Scraper não produziu o arquivo de resultados.")
        return self.read_results(results_file, limit=limit)

    @staticmethod
    def read_results(path: Path, *, limit: int) -> list[dict[str, Any]]:
        if path.stat().st_size > 10_000_000:
            raise MapsScraperError("Resultado do Google Maps excedeu o limite de 10 MB.")
        businesses: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                required = {"title", "link", "website", "phone"}
                if not reader.fieldnames or not required <= set(reader.fieldnames):
                    raise MapsScraperError("Formato CSV do Google Maps Scraper incompatível.")
                for row in reader:
                    name = (row.get("title") or "").strip()[:300]
                    link = _public_url(row.get("link") or "")
                    if not name or not link or link in seen:
                        continue
                    seen.add(link)
                    try:
                        rating = min(5.0, max(0.0, float(row.get("review_rating") or 0)))
                        review_count = max(0, int(row.get("review_count") or 0))
                    except (ValueError, OverflowError):
                        rating, review_count = 0.0, 0
                    businesses.append({
                        "name": name, "maps_url": link,
                        "phone": (row.get("phone") or "").strip()[:100],
                        "whatsapp": "",  # A Maps phone is not proof of WhatsApp registration.
                        "address": (row.get("address") or "").strip()[:1000],
                        # Preserve a nonempty unrecognized website as evidence of a site;
                        # dropping it would falsely qualify a business as having no site.
                        "website": (row.get("website") or "").strip()[:2048],
                        "category": (row.get("category") or "").strip()[:300],
                        "rating": rating, "review_count": review_count,
                        "source": "gosom/google-maps-scraper",
                    })
                    if len(businesses) >= limit:
                        break
        except (csv.Error, UnicodeError) as exc:
            raise MapsScraperError("Não foi possível interpretar o CSV do Google Maps.") from exc
        return businesses
