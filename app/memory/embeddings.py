from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol


class EmbeddingProvider(Protocol):
    """Optional local or remote adapter; SQLite storage does not depend on one."""

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


class LocalHashEmbeddingProvider:
    """Deterministic local feature hashing; no model download or data egress."""

    def __init__(self, dimensions: int = 384) -> None:
        if dimensions < 32:
            raise ValueError("dimensions must be at least 32")
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"\w+", text.casefold(), flags=re.UNICODE):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            value = int.from_bytes(digest)
            vector[value % self.dimensions] += -1.0 if value & 1 else 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
