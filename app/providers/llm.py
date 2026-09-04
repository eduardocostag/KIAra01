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
            with tempfile.NamedTemporaryFile(
                prefix="kiara-vision-", suffix=suffix, delete=False
            ) as tmp:
                tmp.write(image)
                path = Path(tmp.name)
            return await self.vision(prompt, path)
        finally:
            if path is not None:
                path.unlink(missing_ok=True)

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"generate"})


class FallbackProvider(LLMProvider):
    """Tries providers in order so a free-tier limit does not stop Kiara."""

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("É necessário pelo menos um provedor.")
        self.providers = providers

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset().union(*(provider.capabilities for provider in self.providers))

    async def generate(self, prompt: str) -> str:
        return await self._try("generate", prompt)

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        errors: list[Exception] = []
        for provider in self.providers:
            emitted = False
            try:
                async for delta in provider.stream(prompt):
                    emitted = True
                    yield delta
                return
            except Exception as exc:
                if emitted:
                    raise RuntimeError("O streaming falhou após iniciar a resposta.") from exc
                errors.append(exc)
        raise RuntimeError("Nenhum provedor de IA conseguiu responder.") from (
            errors[-1] if errors else None
        )

    async def vision_bytes(
        self, prompt: str, image: bytes, *, media_type: str = "image/png"
    ) -> str:
        errors: list[Exception] = []
        for provider in self.providers:
            if "vision" not in provider.capabilities:
                continue
            try:
                return await provider.vision_bytes(prompt, image, media_type=media_type)
            except Exception as exc:  # noqa: BLE001 - fallback boundary
                errors.append(exc)
        raise RuntimeError("Nenhum provedor visual conseguiu responder.") from (
            errors[-1] if errors else None
        )

    async def _try(self, method: str, prompt: str) -> str:
        errors: list[Exception] = []
        for provider in self.providers:
            try:
                return await getattr(provider, method)(prompt)
            except Exception as exc:  # noqa: BLE001 - fallback boundary
                errors.append(exc)
        raise RuntimeError("Nenhum provedor de IA conseguiu responder.") from (
            errors[-1] if errors else None
        )


class LocalFallbackProvider(LLMProvider):
    async def generate(self, prompt: str) -> str:
        return "O provedor de IA ainda não foi configurado. Posso executar ferramentas locais permitidas."
