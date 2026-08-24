from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any

from app.agents.contracts import Specialist, SpecialistResult
from app.agents.specialists import (
    GeneralistSpecialist,
    ProductivitySpecialist,
    ResearchSpecialist,
    SecuritySpecialist,
    SoftwareSpecialist,
)
from app.providers.llm import LLMProvider


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
                SecuritySpecialist(),
                ProductivitySpecialist(),
                ResearchSpecialist(),
            )
        )
        self.generalist = generalist or GeneralistSpecialist()
        self.max_specialists = max_specialists

    def select(self, message: str) -> tuple[Specialist, ...]:
        ranked = sorted(
            ((specialist.score(message), specialist) for specialist in self.specialists),
            key=lambda item: item[0],
            reverse=True,
        )
        selected = tuple(item[1] for item in ranked if item[0] > 0)[: self.max_specialists]
        return selected or (self.generalist,)

    async def respond(self, message: str, context: dict[str, Any]) -> str:
        selected = self.select(message)
        outcomes = await asyncio.gather(
            *(self._consult(specialist, message, context) for specialist in selected)
        )
        results = tuple(result for result in outcomes if result is not None)
        if not results and self.generalist not in selected:
            fallback = await self._consult(self.generalist, message, context)
            results = (fallback,) if fallback is not None else ()
        if not results:
            return (
                "Não consegui consultar um especialista agora. Posso tentar novamente "
                "ou responder de forma mais simples se você reformular o pedido."
            )
        if len(results) == 1:
            return results[0].content
        return await self._compose(message, results)

    async def _consult(
        self, specialist: Specialist, message: str, context: dict[str, Any]
    ) -> SpecialistResult | None:
        try:
            return await asyncio.wait_for(
                specialist.respond(self.provider, message, context), timeout=45
            )
        except Exception:  # noqa: BLE001 - isolate a failed specialist branch
            return None

    async def _compose(self, message: str, results: Sequence[SpecialistResult]) -> str:
        prompt = {
            "role": "coordenador_de_especialistas",
            "user_message": message,
            "specialist_analyses": [
                {"specialist": result.specialist, "content": result.content}
                for result in results
            ],
            "instructions": (
                "Produza uma resposta única e coerente. Resolva conflitos explicitamente, "
                "preserve ressalvas e não alegue ações não executadas."
            ),
        }
        return await self.provider.generate(json.dumps(prompt, ensure_ascii=False))
