from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.memory.embeddings import EmbeddingProvider, cosine_similarity


@dataclass(frozen=True, slots=True)
class IngestReport:
    document_id: int
    chunks_added: int
    deduplicated: bool


@dataclass(frozen=True, slots=True)
class KnowledgeResult:
    content: str
    source: str
    chunk_index: int
    metadata: dict[str, Any]
    score: float
    citation: dict[str, Any]


TextExtractor = Callable[[Path], str]


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError('Instale suporte a PDF com: pip install -e ".[knowledge]"') from exc
    return "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def chunk_text(text: str, size: int = 1_200, overlap: int = 150) -> list[str]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Chunk size/overlap inválidos.")
    normalized = re.sub(r"[ \t]+", " ", text).strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + size, len(normalized))
        if end < len(normalized):
            boundary = max(normalized.rfind("\n", start, end), normalized.rfind(". ", start, end))
            if boundary > start + size // 2:
                end = boundary + 1
        chunks.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start = end - overlap
    return chunks


class KnowledgeStore:
    def __init__(
        self,
        database: str | Path,
        embedding_provider: EmbeddingProvider | None = None,
        chunk_size: int = 1_200,
        chunk_overlap: int = 150,
        extractors: dict[str, TextExtractor] | None = None,
        relevance_threshold: float = 0.1,
        max_chunks_per_source: int = 2,
    ) -> None:
        if not 0 <= relevance_threshold <= 1:
            raise ValueError("relevance_threshold must be between zero and one")
        if max_chunks_per_source <= 0:
            raise ValueError("max_chunks_per_source must be greater than zero")
        path = Path(database)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        # Runtime serializes use on its core loop, which differs from the bootstrap thread.
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._embedding_provider = embedding_provider
        self.chunk_size, self.chunk_overlap = chunk_size, chunk_overlap
        self.relevance_threshold = relevance_threshold
        self.max_chunks_per_source = max_chunks_per_source
        self._extractors = {".txt": self._plain_text, ".md": self._plain_text, ".pdf": _extract_pdf}
        self._extractors.update(extractors or {})
        self._fts = self._initialize()

    def _initialize(self) -> bool:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY, source TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE,
                metadata TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id),
                chunk_index INTEGER NOT NULL, content TEXT NOT NULL, chunk_hash TEXT NOT NULL,
                embedding TEXT, UNIQUE(document_id, chunk_index), UNIQUE(document_id, chunk_hash)
            );
            """
        )
        try:
            self._connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(chunk_id UNINDEXED, content)"
            )
        except sqlite3.OperationalError:
            return False
        return True

    @staticmethod
    def _plain_text(path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    def ingest(self, path: str | Path, metadata: dict[str, Any] | None = None) -> IngestReport:
        source = Path(path).resolve()
        extractor = self._extractors.get(source.suffix.casefold())
        if extractor is None:
            raise ValueError(f"Formato não suportado: {source.suffix}")
        raw = source.read_bytes()
        content_hash = hashlib.sha256(raw).hexdigest()
        existing = self._connection.execute(
            "SELECT id FROM documents WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        if existing:
            return IngestReport(int(existing["id"]), 0, True)
        text = extractor(source)
        chunks = chunk_text(text, self.chunk_size, self.chunk_overlap)
        if not chunks:
            raise ValueError("Documento não contém texto extraível.")
        document_metadata = {"filename": source.name, "extension": source.suffix.casefold()}
        document_metadata.update(metadata or {})
        with self._connection:
            cursor = self._connection.execute(
                "INSERT INTO documents(source, content_hash, metadata) VALUES (?, ?, ?)",
                (str(source), content_hash, json.dumps(document_metadata, ensure_ascii=False)),
            )
            document_id = int(cursor.lastrowid)
            embeddings = (
                self._embedding_provider.embed(chunks) if self._embedding_provider is not None else [None] * len(chunks)
            )
            for index, (content, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                chunk_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                cursor = self._connection.execute(
                    "INSERT OR IGNORE INTO chunks(document_id, chunk_index, content, chunk_hash, embedding) VALUES (?, ?, ?, ?, ?)",
                    (document_id, index, content, chunk_hash, json.dumps(embedding) if embedding is not None else None),
                )
                if self._fts and cursor.rowcount:
                    self._connection.execute(
                        "INSERT INTO knowledge_fts(chunk_id, content) VALUES (?, ?)",
                        (cursor.lastrowid, content),
                    )
        return IngestReport(document_id, len(chunks), False)

    def search(
        self,
        query: str,
        limit: int = 5,
        *,
        relevance_threshold: float | None = None,
    ) -> list[KnowledgeResult]:
        if not query.strip() or limit <= 0:
            return []
        threshold = (
            self.relevance_threshold if relevance_threshold is None else relevance_threshold
        )
        if not 0 <= threshold <= 1:
            raise ValueError("relevance_threshold must be between zero and one")
        lexical: dict[int, float] = {}
        tokens = re.findall(r"\w+", query, flags=re.UNICODE)
        if self._fts and tokens:
            expression = " OR ".join(f'"{token}"' for token in tokens)
            rows = self._connection.execute(
                "SELECT chunk_id, bm25(knowledge_fts) rank FROM knowledge_fts WHERE knowledge_fts MATCH ? LIMIT ?",
                (expression, max(limit * 5, 20)),
            ).fetchall()
            lexical = {int(row["chunk_id"]): 1.0 / (1.0 + abs(float(row["rank"]))) for row in rows}
        query_embedding = None
        if self._embedding_provider is not None:
            query_embedding = self._embedding_provider.embed([query])[0]
        rows = self._connection.execute(
            "SELECT c.*, d.source, d.metadata FROM chunks c JOIN documents d ON d.id = c.document_id"
        ).fetchall()
        query_terms = {term.casefold() for term in tokens}
        results = []
        for row in rows:
            terms = set(re.findall(r"\w+", row["content"].casefold()))
            fallback_lexical = len(query_terms & terms) / max(len(query_terms), 1)
            lexical_score = max(lexical.get(int(row["id"]), 0.0), fallback_lexical)
            semantic = 0.0
            if query_embedding is not None and row["embedding"]:
                semantic = max(0.0, cosine_similarity(query_embedding, json.loads(row["embedding"])))
            score = 0.65 * lexical_score + 0.35 * semantic
            if score >= threshold:
                metadata = json.loads(row["metadata"])
                results.append(
                    KnowledgeResult(
                        row["content"],
                        row["source"],
                        row["chunk_index"],
                        metadata,
                        score,
                        self._citation(row["source"], row["chunk_index"], metadata),
                    )
                )
        return self._diversify(results, limit)

    def backfill_embeddings(self, *, batch_size: int = 16) -> int:
        """Populate vectors for previously indexed chunks without reingesting source files."""
        if self._embedding_provider is None:
            return 0
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        rows = self._connection.execute(
            "SELECT id, content FROM chunks WHERE embedding IS NULL ORDER BY id"
        ).fetchall()
        updated = 0
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            vectors = self._embedding_provider.embed([str(row["content"]) for row in batch])
            if len(vectors) != len(batch):
                raise RuntimeError("Provider retornou uma quantidade incorreta de embeddings.")
            with self._connection:
                self._connection.executemany(
                    "UPDATE chunks SET embedding = ? WHERE id = ?",
                    (
                        (json.dumps(list(vector)), int(row["id"]))
                        for row, vector in zip(batch, vectors, strict=True)
                    ),
                )
            updated += len(batch)
        return updated

    def _diversify(self, results: list[KnowledgeResult], limit: int) -> list[KnowledgeResult]:
        """Remove repeated chunks and prevent one document from monopolizing context."""
        selected: list[KnowledgeResult] = []
        seen_content: set[str] = set()
        source_counts: dict[str, int] = {}
        for result in sorted(results, key=lambda item: item.score, reverse=True):
            fingerprint = hashlib.sha256(
                re.sub(r"\s+", " ", result.content).strip().casefold().encode("utf-8")
            ).hexdigest()
            if fingerprint in seen_content:
                continue
            if source_counts.get(result.source, 0) >= self.max_chunks_per_source:
                continue
            seen_content.add(fingerprint)
            source_counts[result.source] = source_counts.get(result.source, 0) + 1
            selected.append(result)
            if len(selected) == limit:
                break
        return selected

    @staticmethod
    def _citation(source: str, chunk_index: int, metadata: dict[str, Any]) -> dict[str, Any]:
        citation: dict[str, Any] = {"source": source, "chunk": chunk_index}
        page = metadata.get("page", metadata.get("page_number"))
        if page is not None:
            citation["page"] = page
        return citation

    def close(self) -> None:
        self._connection.close()

    def document_count(self) -> int:
        with sqlite3.connect(self.path) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])

    def chunk_count(self) -> int:
        with sqlite3.connect(self.path) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])

    def list_documents(self, *, limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        rows = self._connection.execute(
            """SELECT d.id, d.source, d.metadata, COUNT(c.id) AS chunks
               FROM documents d LEFT JOIN chunks c ON c.document_id = d.id
               GROUP BY d.id ORDER BY d.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "source": str(row["source"]),
                "metadata": json.loads(row["metadata"]),
                "chunks": int(row["chunks"]),
            }
            for row in rows
        ]

    def forget_document(self, document_id: int) -> bool:
        with self._connection:
            chunk_rows = self._connection.execute(
                "SELECT id FROM chunks WHERE document_id = ?", (document_id,)
            ).fetchall()
            if self._fts and chunk_rows:
                self._connection.executemany(
                    "DELETE FROM knowledge_fts WHERE chunk_id = ?",
                    ((int(row["id"]),) for row in chunk_rows),
                )
            self._connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            cursor = self._connection.execute(
                "DELETE FROM documents WHERE id = ?", (document_id,)
            )
        return cursor.rowcount > 0
