from __future__ import annotations

import json
import re
import time
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass

from app.observability import MetricsRegistry
from app.providers.llm import LLMProvider


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    profile: str
    reason: str


class LocalProfilePolicy:
    """Deterministic policy; it never calls a model or external service."""

    _REASONING_MARKERS = re.compile(
        r"\b(analise|arquitetura|compare|diagnostique|estrategia|planeje|"
        r"explique(?: por que)?|por que|como (?:posso|funciona|resolver)|qual (?:é|e) a diferença|"
        r"o que devo|me ensine|me ajude a|resolva|calcule|avalie|demonstre|vantagens|"
        r"desvantagens|passo a passo|trade-?off|debug|investigue)\b",
        re.IGNORECASE,
    )
    _CODE_MARKERS = re.compile(
        r"```|traceback|exception|\b(class|def|async|sql|api)\b", re.IGNORECASE
    )

    def __init__(self, *, reasoning_chars: int = 1_200) -> None:
        self.reasoning_chars = max(100, reasoning_chars)

    def select_text(self, prompt: str) -> RoutingDecision:
        user_text = self._user_text(prompt)
        if len(user_text) >= self.reasoning_chars:
            return RoutingDecision("reasoning", "long_input")
        if self._REASONING_MARKERS.search(user_text) or self._CODE_MARKERS.search(user_text):
            return RoutingDecision("reasoning", "complexity_marker")
        return RoutingDecision("fast", "default")

    @staticmethod
    def _user_text(prompt: str) -> str:
        try:
            payload = json.loads(prompt)
        except (json.JSONDecodeError, TypeError):
            return prompt
        if not isinstance(payload, dict):
            return prompt
        for key in ("user_message", "message", "prompt"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        return prompt


class ModelRouter(LLMProvider):
    """Opt-in router over already-created providers.

    Construction has no side effects: callers remain responsible for creating local or remote
    providers and explicitly choosing to wrap them.
    """

    REQUIRED_PROFILES = frozenset({"fast", "reasoning"})

    def __init__(
        self,
        profiles: Mapping[str, LLMProvider],
        *,
        policy: LocalProfilePolicy | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        missing = self.REQUIRED_PROFILES - profiles.keys()
        if missing:
            raise ValueError(f"Perfis obrigatórios ausentes: {', '.join(sorted(missing))}")
        self.profiles = dict(profiles)
        self.policy = policy or LocalProfilePolicy()
        self.metrics = metrics or MetricsRegistry()
        self.last_decision: RoutingDecision | None = None

    @property
    def capabilities(self) -> frozenset[str]:
        capabilities = {"generate"}
        vision = self.profiles.get("vision")
        if vision is not None and "vision" in vision.capabilities:
            capabilities.add("vision")
        return frozenset(capabilities)

    async def generate(self, prompt: str) -> str:
        decision = self.policy.select_text(prompt)
        return await self._generate_with(decision, prompt)

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        decision = self.policy.select_text(prompt)
        self._record_decision(decision)
        provider = self.profiles[decision.profile]
        started = time.perf_counter()
        try:
            async for chunk in provider.stream(prompt):
                yield chunk
        except Exception:
            self.metrics.increment(f"model_router.error.{decision.profile}")
            raise
        finally:
            self.metrics.observe(
                f"model_router.latency.{decision.profile}",
                (time.perf_counter() - started) * 1_000,
            )

    async def vision_bytes(
        self, prompt: str, image: bytes, *, media_type: str = "image/png"
    ) -> str:
        provider = self.profiles.get("vision")
        if provider is None or "vision" not in provider.capabilities:
            raise RuntimeError("O perfil visual opt-in não está configurado.")
        decision = RoutingDecision("vision", "vision_input")
        self._record_decision(decision)
        started = time.perf_counter()
        try:
            return await provider.vision_bytes(prompt, image, media_type=media_type)
        except Exception:
            self.metrics.increment("model_router.error.vision")
            raise
        finally:
            self.metrics.observe(
                "model_router.latency.vision", (time.perf_counter() - started) * 1_000
            )

    async def _generate_with(self, decision: RoutingDecision, prompt: str) -> str:
        self._record_decision(decision)
        started = time.perf_counter()
        try:
            return await self.profiles[decision.profile].generate(prompt)
        except Exception:
            self.metrics.increment(f"model_router.error.{decision.profile}")
            raise
        finally:
            self.metrics.observe(
                f"model_router.latency.{decision.profile}",
                (time.perf_counter() - started) * 1_000,
            )

    def _record_decision(self, decision: RoutingDecision) -> None:
        self.last_decision = decision
        self.metrics.increment(f"model_router.route.{decision.profile}")
