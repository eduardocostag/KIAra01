from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.security.redaction import redact


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def record(self, **fields: Any) -> None:
        entry = {"timestamp": datetime.now(UTC).isoformat(), **redact(fields)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def read(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """Read a bounded, newest-first timeline; tolerate an interrupted final line."""
        limit = min(1000, max(1, int(limit)))
        if not self.path.exists():
            return []
        entries: list[dict[str, Any]] = []
        with self._lock, self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    entries.append(value)
        return entries[-limit:][::-1]

    def export(self, destination: Path, *, limit: int = 1000) -> int:
        """Export an already-redacted snapshot and never overwrite the live log."""
        if destination.resolve() == self.path.resolve():
            raise ValueError("Audit export destination must differ from the live log")
        entries = self.read(limit=limit)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "\n".join(
                json.dumps(item, ensure_ascii=False, default=str) for item in reversed(entries)
            )
            + ("\n" if entries else ""),
            encoding="utf-8",
        )
        return len(entries)
