from __future__ import annotations

from typing import Any

from ..http.context import RequestContext
from ..http.errors import ApiError
from ..ports.pipeline import PipelineRepository

_ALLOWED_ROLES = {"owner", "admin", "operator"}


class PipelineService:
    def __init__(self, repository: PipelineRepository) -> None:
        self._repository = repository

    @staticmethod
    def require_operator(context: RequestContext) -> None:
        if context.role not in _ALLOWED_ROLES:
            raise ApiError(403, "insufficient_role", "Acesso restrito a operadores.")

    async def list_entries(self, context: RequestContext) -> list[dict[str, Any]]:
        self.require_operator(context)
        return await self._repository.list_entries(context.organization_id)

    async def update_entry(
        self,
        context: RequestContext,
        entry_id: str,
        idempotency_key: str,
        expected_version: int,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        self.require_operator(context)
        outcome, entry = await self._repository.update_entry(
            context.organization_id, entry_id, idempotency_key, expected_version, changes
        )
        if outcome == "missing":
            raise ApiError(404, "pipeline_entry_not_found", "Entrada não encontrada.")
        if outcome == "conflict":
            raise ApiError(412, "version_conflict", "A entrada foi alterada por outro usuário.")
        if outcome == "idempotency_conflict":
            raise ApiError(409, "idempotency_conflict", "Chave de idempotência já utilizada.")
        assert entry is not None
        return entry
