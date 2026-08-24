from __future__ import annotations

import tempfile
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        yield await self.generate(prompt)

    async def vision(self, prompt: str, image: Path) -> str:
        raise NotImplementedError("Este provider não oferece visão.")

    async def vision_bytes(
        self, prompt: str, image: bytes, *, media_type: str = "image/png"
    ) -> str:
        """Analyze ephemeral pixels and remove the compatibility file immediately."""
        suffix = ".png" if media_type == "image/png" else ".img"
        path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="kiara-vision-", suffix=suffix, delete=False) as tmp:
                tmp.write(image)
                path = Path(tmp.name)
            return await self.vision(prompt, path)
        finally:
            if path is not None:
                path.unlink(missing_ok=True)

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"generate"})


class LocalFallbackProvider(LLMProvider):
    async def generate(self, prompt: str) -> str:
        return "O provedor de IA ainda não foi configurado. Posso executar ferramentas locais permitidas."
