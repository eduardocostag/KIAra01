from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

from app.agents.contracts import Specialist, SpecialistResult
from app.agents.specialists import (
    DataSystemsSpecialist,
    GeneralistSpecialist,
    HelpdeskSpecialist,
    InfrastructureSpecialist,
    ProductivitySpecialist,
    ResearchSpecialist,
    SalesDevelopmentSpecialist,
    SecuritySpecialist,
    SoftwareSpecialist,
)
from app.providers.llm import LLMProvider


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    specialists: tuple[Specialist, ...]
    confidence: float
    scores: dict[str, int]


class AgentRouter:
    def __init__(
        self,
        provider: LLMProvider,
        specialists: Sequence[Specialist] | None = None,
        generalist: Specialist | None = None,
        max_specialists: int = 3,
    ) -> None:
        self.provider = provider
        self.specialists = tuple(
            specialists
            or (
                SoftwareSpecialist(),
                DataSystemsSpecialist(),
                HelpdeskSpecialist(),
                InfrastructureSpecialist(),
                SecuritySpecialist(),
                ProductivitySpecialist(),
                ResearchSpecialist(),
                SalesDevelopmentSpecialist(),
            )
        )
        self.generalist = generalist or GeneralistSpecialist()
        self.max_specialists = max_specialists

    def select(self, message: str) -> tuple[Specialist, ...]:
        return self.decide(message).specialists

    def decide(self, message: str) -> RoutingDecision:
        ranked = sorted(
            ((specialist.score(message), specialist) for specialist in self.specialists),
            key=lambda item: item[0],
            reverse=True,
        )
        selected = tuple(item[1] for item in ranked if item[0] > 0)[: self.max_specialists]
        if not selected:
            return RoutingDecision((self.generalist,), 0.0, {})
        # A clearly dominant domain does not benefit from duplicate consultations. This also
        # prevents concurrent requests from contending for the same local Ollama model.
        if len(selected) > 1 and ranked[0][0] >= ranked[1][0] + 2:
            selected = selected[:1]
        positive = {specialist.name: score for score, specialist in ranked if score > 0}
        top_score = ranked[0][0]
        total = sum(positive.values())
        confidence = min(1.0, top_score / max(1, total) + min(top_score, 3) * 0.1)
        return RoutingDecision(selected, round(confidence, 3), positive)

    async def respond(self, message: str, context: dict[str, Any]) -> str:
        selected = self.select(message)
        outcomes = await asyncio.gather(
            *(self._consult(specialist, message, context) for specialist in selected)
        )
        results = tuple(result for result in outcomes if result is not None)
        if not results:
            return (
                "Não consegui consultar um especialista agora. Posso tentar novamente "
                "ou responder de forma mais simples se você reformular o pedido."
            )
        if len(results) == 1:
            return results[0].content
        return await self._compose(message, results)

    async def stream_respond(self, message: str, context: dict[str, Any]) -> AsyncIterator[str]:
        selected = self.select(message)
        if len(selected) == 1:
            emitted = False
            try:
                async for delta in selected[0].stream_respond(self.provider, message, context):
                    emitted = True
                    yield delta
                if emitted:
                    return
            except Exception:
                if emitted:
                    raise
        yield await self.respond(message, context)

    async def _consult(
        self, specialist: Specialist, message: str, context: dict[str, Any]
    ) -> SpecialistResult | None:
        try:
            return await asyncio.wait_for(
                specialist.respond(self.provider, message, context), timeout=100
            )
        except Exception:  # noqa: BLE001 - isolate a failed specialist branch
            return None

    async def _compose(self, message: str, results: Sequence[SpecialistResult]) -> str:
        prompt = {
            "role": "coordenador_de_especialistas",
            "user_message": message,
            "specialist_analyses": [
                {
                    "specialist": result.specialist,
                    "content": self._composition_excerpt(result.content),
                }
                for result in results
            ],
            "instructions": (
                "Produza uma resposta única e coerente. Resolva conflitos explicitamente, "
                "preserve ressalvas e não alegue ações não executadas. Cubra cada parte "
                "pedida pelo usuário, inclusive critérios, etapas e conclusões que apareçam "
                "no fim das análises. Elimine repetições e seja conciso."
            ),
        }
        try:
            generate_profile = getattr(self.provider, "generate_for_profile", None)
            generation = (
                generate_profile("fast", json.dumps(prompt, ensure_ascii=False))
                if callable(generate_profile)
                else self.provider.generate(json.dumps(prompt, ensure_ascii=False))
            )
            return await asyncio.wait_for(
                generation, timeout=60
            )
        except Exception:  # noqa: BLE001 - preserve useful specialist work on compose failure
            return self._unsynthesized(results)

    @staticmethod
    def _composition_excerpt(content: str, limit: int = 4000) -> str:
        """Keep both reasoning premises and conclusions within a bounded coordinator prompt."""
        if len(content) <= limit:
            return content
        head = int(limit * 0.6)
        tail = limit - head
        return content[:head] + "\n\n[trecho intermediário condensado]\n\n" + content[-tail:]

    @staticmethod
    def _unsynthesized(results: Sequence[SpecialistResult]) -> str:
        sections = [f"### {result.specialist}\n\n{result.content[:5000]}" for result in results]
        return (
            "As análises já são extensas; seguem separadas para preservar detalhes sem "
            "alegar consenso artificial:\n\n" + "\n\n".join(sections)
        )
