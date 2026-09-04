from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.security.redaction import redact_text


class CorrectionInbox:
    """Local, append-only queue of answers the user marked as unhelpful."""

    def __init__(self, path: Path, *, max_text_chars: int = 20_000) -> None:
        self.path = path.resolve()
        self.max_text_chars = max(1, max_text_chars)
        self._lock = threading.Lock()

    def add(self, user_message: str, assistant_response: str) -> str:
        correction_id = str(uuid4())
        record = {
            "id": correction_id,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "pending",
            "reason": "user_reported_not_helpful",
            "user_message": self._safe_text(user_message),
            "assistant_response": self._safe_text(assistant_response),
        }
        serialized = json.dumps(record, ensure_ascii=False)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as destination:
                destination.write(f"{serialized}\n")
        return correction_id

    def pending_count(self) -> int:
        if not self.path.exists():
            return 0
        count = 0
        with self._lock, self.path.open(encoding="utf-8") as source:
            for line in source:
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                if record.get("status") == "pending":
                    count += 1
        return count

    def _safe_text(self, value: str) -> str:
        return redact_text(value.strip())[: self.max_text_chars]
