from __future__ import annotations

import pytest

from app.agents.router import AgentRouter
from app.agents.specialists import GeneralistSpecialist
from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.models import ScreenContext, ToolResult
from tests.test_conversation_context import RecordingProvider


class CalendarTools:
    def __init__(self, names: tuple[str, ...]) -> None:
        self._names = names
        self.calls: list[tuple[str, dict[str, object]]] = []

    def names(self) -> tuple[str, ...]:
        return self._names

    async def execute(self, name: str, **parameters: object) -> ToolResult:
        self.calls.append((name, parameters))
        return ToolResult(True, output="Nenhum compromisso futuro.")


def core_with(tools: CalendarTools) -> AgentCore:
    provider = RecordingProvider()
    return AgentCore(
        tools,
        provider,
        ContextManager(lambda: ScreenContext()),
        agent_router=AgentRouter(provider, specialists=(), generalist=GeneralistSpecialist()),
    )


@pytest.mark.asyncio
async def test_week_calendar_reads_local_agenda_with_end_date() -> None:
    tools = CalendarTools(("list_personal_events",))

    response = await core_with(tools).handle("veja meu calendário da semana")

    assert tools.calls[0][0] == "list_personal_events"
    assert set(tools.calls[0][1]) == {"from_at", "to_at"}
    assert response.startswith("Agenda local da Kiara")


@pytest.mark.asyncio
async def test_teams_calendar_is_honest_when_graph_is_not_connected() -> None:
    tools = CalendarTools(("list_personal_events",))

    response = await core_with(tools).handle("veja minhas reuniões do teams essa semana")

    assert tools.calls == []
    assert "Microsoft Graph" in response
    assert "não está conectada" in response
