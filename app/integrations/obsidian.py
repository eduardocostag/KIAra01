from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from app.knowledge import KnowledgeStore


@dataclass(frozen=True, slots=True)
class ObsidianSyncReport:
    scanned: int
    indexed: int
    unchanged: int
    removed: int
    private_skipped: int


class ObsidianVaultIndex:
    """Read-only, incremental bridge from an Obsidian vault to local knowledge."""

    def __init__(
        self,
        vault: str | Path,
        knowledge: KnowledgeStore,
        state_path: str | Path,
        *,
        excluded_directories: tuple[str, ...] = (".obsidian", ".trash"),
        private_directories: tuple[str, ...] = ("90 - Privado",),
        max_file_bytes: int = 2_000_000,
    ) -> None:
        self.vault = Path(vault).expanduser().resolve()
        if not self.vault.is_dir():
            raise ValueError("O vault do Obsidian não existe ou não é uma pasta.")
        self.knowledge = knowledge
        self.state_path = Path(state_path)
        self.excluded_directories = frozenset(excluded_directories)
        self.private_directories = frozenset(private_directories)
        self.max_file_bytes = max(1_024, max_file_bytes)
        self._lock = threading.RLock()

    def sync(self) -> ObsidianSyncReport:
        with self._lock:
            return self._sync_locked()

    def _sync_locked(self) -> ObsidianSyncReport:
        previous = self._load_state()
        current: dict[str, dict[str, object]] = {}
        scanned = indexed = unchanged = private_skipped = 0
        for path in self._markdown_files():
            scanned += 1
            relative = path.relative_to(self.vault).as_posix()
            raw = path.read_bytes()
            if len(raw) > self.max_file_bytes:
                continue
            content = raw.decode("utf-8", errors="replace")
            if self._is_private(content):
                private_skipped += 1
                continue
            digest = hashlib.sha256(raw).hexdigest()
            old = previous.get(relative)
            if old and old.get("hash") == digest:
                current[relative] = old
                unchanged += 1
                continue
            report = self.knowledge.ingest(
                path,
                {
                    "integration": "obsidian",
                    "vault": self.vault.name,
                    "relative_path": relative,
                    "obsidian_uri": self.note_uri(relative),
                },
            )
            current[relative] = {"hash": digest, "document_id": report.document_id}
            indexed += 1
            if old and isinstance(old.get("document_id"), int):
                self.knowledge.forget_document(int(old["document_id"]))
        removed_entries = [entry for name, entry in previous.items() if name not in current]
        removed = 0
        for entry in removed_entries:
            document_id = entry.get("document_id")
            if isinstance(document_id, int) and self.knowledge.forget_document(document_id):
                removed += 1
        self._write_state(current)
        return ObsidianSyncReport(scanned, indexed, unchanged, removed, private_skipped)

    def note_uri(self, relative_path: str) -> str:
        note = relative_path[:-3] if relative_path.casefold().endswith(".md") else relative_path
        return f"obsidian://open?vault={quote(self.vault.name)}&file={quote(note, safe='')}"

    def diagnostics(self) -> dict[str, object]:
        return {
            "enabled": True,
            "vault": str(self.vault),
            "read_only": True,
            "state": str(self.state_path),
        }

    def _markdown_files(self):
        for path in sorted(self.vault.rglob("*.md")):
            try:
                resolved = path.resolve()
                resolved.relative_to(self.vault)
            except (OSError, ValueError):
                continue
            if any(
                part in self.excluded_directories or part in self.private_directories
                for part in path.relative_to(self.vault).parts
            ):
                continue
            if path.is_file():
                yield path

    @classmethod
    def _is_private(cls, content: str) -> bool:
        if not content.startswith("---"):
            return False
        _, separator, _rest = content[3:].partition("---")
        if not separator:
            return False
        frontmatter = content[3 : content.find("---", 3)]
        for line in frontmatter.splitlines():
            key, marker, value = line.partition(":")
            if not marker:
                continue
            normalized_key = key.strip().casefold()
            normalized_value = value.strip().casefold()
            if normalized_key in {"private", "kiara_private"} and normalized_value == "true":
                return True
            if normalized_key in {"kiara", "kiara_index"} and normalized_value in {
                "false",
                "private",
            }:
                return True
        return False

    def _load_state(self) -> dict[str, dict[str, object]]:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        entries = payload.get("files", {}) if isinstance(payload, dict) else {}
        return entries if isinstance(entries, dict) else {}

    def _write_state(self, files: dict[str, dict[str, object]]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {"version": 1, "vault": str(self.vault), "files": files},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)


class ObsidianSyncService:
    def __init__(self, index: ObsidianVaultIndex, *, interval_seconds: float = 10.0) -> None:
        self.index = index
        self.interval_seconds = max(2.0, interval_seconds)
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="obsidian-sync")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def _loop(self) -> None:
        while not self._stop.is_set():
            self.index.sync()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                pass
