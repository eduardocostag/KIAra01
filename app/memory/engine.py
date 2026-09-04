from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.memory.embeddings import EmbeddingProvider, cosine_similarity
from app.memory.models import MemoryKind, MemoryProfile, MemoryRecord

_TOKEN = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


def _serialized(method):
    """Serialize access to the shared SQLite connection across UI/core threads."""

    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


class MemoryEngine:
    """Local SQLite memory with deterministic lexical retrieval and retention."""

    def __init__(
        self,
        path: Path,
        *,
        embedding_provider: EmbeddingProvider | None = None,
        default_ttl: dict[MemoryKind, timedelta | None] | None = None,
        retrieval_limit: int = 5,
    ) -> None:
        if retrieval_limit <= 0:
            raise ValueError("retrieval_limit must be greater than zero")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        # Runtime owns all operations on one durable core loop; creation may occur on the UI thread.
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._embedding_provider = embedding_provider
        self._ttl = default_ttl or {MemoryKind.WORKING: timedelta(hours=24)}
        self.retrieval_limit = retrieval_limit
        self._migrate()

    def _migrate(self) -> None:
        existing = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
        ).fetchone()
        columns = {
            str(row[1])
            for row in self._connection.execute("PRAGMA table_info(memories)").fetchall()
        }
        # Detect the legacy layout by its actual columns.  Looking for enum text
        # in CREATE TABLE is not stable: the v2 schema intentionally has no
        # CHECK enum and would otherwise be destructively migrated on every boot.
        if existing and "profile" not in columns:
            self._connection.executescript(
                """
                ALTER TABLE memories RENAME TO memories_v1;
                CREATE TABLE memories (
                    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, content TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}', importance REAL NOT NULL
                    CHECK(importance BETWEEN 0.0 AND 1.0), created_at TEXT NOT NULL,
                    accessed_at TEXT NOT NULL, expires_at TEXT, embedding TEXT,
                    profile TEXT NOT NULL DEFAULT 'personal', version INTEGER NOT NULL DEFAULT 1,
                    parent_id INTEGER, superseded_by INTEGER, provenance TEXT NOT NULL DEFAULT 'user'
                );
                INSERT INTO memories(id,kind,content,metadata,importance,created_at,accessed_at,
                    expires_at,embedding) SELECT id,kind,content,metadata,importance,created_at,
                    accessed_at,expires_at,embedding FROM memories_v1;
                DROP TABLE memories_v1;
                """
            )
        self._connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                importance REAL NOT NULL CHECK(importance BETWEEN 0.0 AND 1.0),
                created_at TEXT NOT NULL,
                accessed_at TEXT NOT NULL,
                expires_at TEXT,
                embedding TEXT,
                profile TEXT NOT NULL DEFAULT 'personal', version INTEGER NOT NULL DEFAULT 1,
                parent_id INTEGER, superseded_by INTEGER,
                provenance TEXT NOT NULL DEFAULT 'user'
            );
            CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);
            CREATE INDEX IF NOT EXISTS idx_memories_expiry ON memories(expires_at);
            CREATE INDEX IF NOT EXISTS idx_memories_profile ON memories(profile);
            PRAGMA user_version=2;
            """
        )
        self._connection.commit()

    @_serialized
    def remember(
        self,
        kind: MemoryKind,
        content: str,
        *,
        metadata: dict[str, object] | None = None,
        importance: float = 0.5,
        expires_at: datetime | None = None,
        profile: MemoryProfile = MemoryProfile.PERSONAL,
        provenance: str = "user",
        parent_id: int | None = None,
        version: int = 1,
    ) -> int:
        content = content.strip()
        if not content:
            raise ValueError("Memory content cannot be empty")
        if not 0 <= importance <= 1:
            raise ValueError("importance must be between 0 and 1")
        now = datetime.now(UTC)
        if expires_at is None and (ttl := self._ttl.get(kind)) is not None:
            expires_at = now + ttl
        embedding = None
        if self._embedding_provider is not None:
            embedding = list(self._embedding_provider.embed([content])[0])
        cursor = self._connection.execute(
            """INSERT INTO memories
               (kind, content, metadata, importance, created_at, accessed_at, expires_at, embedding,
                profile, provenance, parent_id, version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                kind.value,
                content,
                json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                importance,
                now.isoformat(),
                now.isoformat(),
                expires_at.isoformat() if expires_at else None,
                json.dumps(embedding) if embedding is not None else None,
                profile.value,
                provenance.strip() or "user",
                parent_id,
                version,
            ),
        )
        self._connection.commit()
        return int(cursor.lastrowid)

    @_serialized
    def search(
        self,
        query: str,
        *,
        kinds: Iterable[MemoryKind] | None = None,
        limit: int | None = None,
        now: datetime | None = None,
        profile: MemoryProfile | None = None,
    ) -> list[MemoryRecord]:
        limit = self.retrieval_limit if limit is None else limit
        if limit <= 0:
            return []
        now = now or datetime.now(UTC)
        selected = tuple(kinds or MemoryKind)
        if not selected:
            return []
        placeholders = ",".join("?" for _ in selected)
        rows = self._connection.execute(
            f"""SELECT * FROM memories WHERE kind IN ({placeholders})
                AND (expires_at IS NULL OR expires_at > ?) AND superseded_by IS NULL
                AND (? IS NULL OR profile = ?)""",
            (
                *(kind.value for kind in selected),
                now.isoformat(),
                profile.value if profile else None,
                profile.value if profile else None,
            ),
        ).fetchall()
        query_tokens = self._tokens(query)
        query_embedding = None
        if self._embedding_provider is not None and query.strip():
            query_embedding = self._embedding_provider.embed([query])[0]
        scored: list[MemoryRecord] = []
        for row in rows:
            content_tokens = self._tokens(row["content"])
            lexical = len(query_tokens & content_tokens) / max(1, len(query_tokens))
            created = datetime.fromisoformat(row["created_at"])
            age_days = max(0.0, (now - created).total_seconds() / 86_400)
            recency = math.exp(-age_days / 30)
            semantic = 0.0
            if query_embedding is not None and row["embedding"]:
                semantic = max(
                    0.0, cosine_similarity(query_embedding, json.loads(row["embedding"]))
                )
            score = (
                0.55 * lexical + 0.2 * float(row["importance"]) + 0.15 * recency + 0.1 * semantic
            )
            scored.append(
                self._record(
                    row,
                    score,
                    {
                        "lexical": lexical,
                        "importance": float(row["importance"]),
                        "recency": recency,
                        "semantic": semantic,
                        "total": score,
                    },
                )
            )
        scored.sort(key=lambda item: (item.score, item.created_at), reverse=True)
        result = scored[:limit]
        if result:
            ids = [record.id for record in result]
            self._connection.executemany(
                "UPDATE memories SET accessed_at = ? WHERE id = ?",
                ((now.isoformat(), identifier) for identifier in ids),
            )
            self._connection.commit()
        return result

    @_serialized
    def forget(self, identifier: int) -> bool:
        cursor = self._connection.execute("DELETE FROM memories WHERE id = ?", (identifier,))
        self._connection.commit()
        return cursor.rowcount > 0

    @_serialized
    def revise(self, identifier: int, content: str, *, provenance: str = "user_correction") -> int:
        row = self._connection.execute(
            "SELECT * FROM memories WHERE id = ?", (identifier,)
        ).fetchone()
        if row is None or row["superseded_by"] is not None:
            raise KeyError(identifier)
        new_id = self.remember(
            MemoryKind(row["kind"]),
            content,
            metadata=json.loads(row["metadata"]),
            importance=float(row["importance"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            profile=MemoryProfile(row["profile"]),
            provenance=provenance,
            parent_id=identifier,
            version=int(row["version"]) + 1,
        )
        self._connection.execute(
            "UPDATE memories SET superseded_by = ? WHERE id = ?", (new_id, identifier)
        )
        self._connection.commit()
        return new_id

    @_serialized
    def consolidate(self, identifiers: Iterable[int], content: str) -> int:
        ids = tuple(dict.fromkeys(identifiers))
        if len(ids) < 2:
            raise ValueError("At least two memories are required")
        rows = self._connection.execute(
            f"SELECT * FROM memories WHERE id IN ({','.join('?' for _ in ids)})", ids
        ).fetchall()
        if len(rows) != len(ids) or any(row["superseded_by"] is not None for row in rows):
            raise KeyError("Memory missing or already superseded")
        if len({row["profile"] for row in rows}) != 1:
            raise ValueError("Cannot consolidate across profiles")
        new_id = self.remember(
            MemoryKind.FACT,
            content,
            metadata={"consolidated_from": list(ids)},
            importance=max(float(row["importance"]) for row in rows),
            profile=MemoryProfile(rows[0]["profile"]),
            provenance="consolidation",
        )
        self._connection.executemany(
            "UPDATE memories SET superseded_by = ? WHERE id = ?", ((new_id, item) for item in ids)
        )
        self._connection.commit()
        return new_id

    @_serialized
    def list_records(self, *, limit: int = 100) -> list[MemoryRecord]:
        if limit <= 0:
            return []
        rows = self._connection.execute(
            "SELECT * FROM memories ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._record(row, 0.0) for row in rows]

    @_serialized
    def purge_expired(self, *, now: datetime | None = None) -> int:
        instant = (now or datetime.now(UTC)).isoformat()
        cursor = self._connection.execute(
            "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at <= ?", (instant,)
        )
        self._connection.commit()
        return cursor.rowcount

    @_serialized
    def close(self) -> None:
        self._connection.close()

    def count(self) -> int:
        # UI diagnostics may run outside the core owner thread; use an isolated read connection.
        with sqlite3.connect(self.path) as connection:
            row = connection.execute("SELECT COUNT(*) FROM memories").fetchone()
            return int(row[0])

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token.casefold() for token in _TOKEN.findall(text)}

    @staticmethod
    def _record(
        row: sqlite3.Row, score: float, explanation: dict[str, float] | None = None
    ) -> MemoryRecord:
        return MemoryRecord(
            id=int(row["id"]),
            kind=MemoryKind(row["kind"]),
            content=str(row["content"]),
            metadata=json.loads(row["metadata"]),
            importance=float(row["importance"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            accessed_at=datetime.fromisoformat(row["accessed_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            score=score,
            profile=MemoryProfile(row["profile"]),
            version=int(row["version"]),
            parent_id=row["parent_id"],
            superseded_by=row["superseded_by"],
            provenance=str(row["provenance"]),
            retrieval_explanation=explanation or {},
        )
