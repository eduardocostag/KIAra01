from __future__ import annotations

import json
from typing import Any, ClassVar

import pytest

from app.agents.router import AgentRouter
from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.memory import MemoryEngine
from app.models import AutonomyMode, PermissionLevel, ScreenContext, ToolResult
from app.planning import PlanRejected, TaskPlanner
from app.providers.llm import LLMProvider
from app.security.audit import AuditLog
from app.security.permissions import PermissionGate
from app.tools.base import Tool
from app.tools.registry import ToolRegistry


class SequenceProvider(LLMProvider):
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.prompts: list[dict] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(json.loads(prompt))
        return self.responses.pop(0)


class SchemaTool(Tool):
    name = "schema_action"
    description = "A bounded test action"
    permission_level = PermissionLevel.SAFE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    }

    def __init__(self, outcomes: list[ToolResult] | None = None) -> None:
        self.outcomes = outcomes or [ToolResult(True, output="done", metadata={"verified": True})]
        self.calls = 0

    def validate(self, parameters):
        if set(parameters) != {"value"} or not isinstance(parameters["value"], str):
            raise ValueError("invalid schema_action parameters")

    async def execute(self, **parameters):
        self.calls += 1
        return self.outcomes.pop(0)


class SensitiveSchemaTool(SchemaTool):
    name = "sensitive_action"
    permission_level = PermissionLevel.SENSITIVE_ACTION


def make_registry(tmp_path, tool: Tool) -> ToolRegistry:
    registry = ToolRegistry(
        PermissionGate(AutonomyMode.AUTONOMOUS, confirm=lambda _: True),
        AuditLog(tmp_path / "audit.jsonl"),
    )
    registry.register(tool)
    return registry


def plan(tool: str = "schema_action", retry_count: int = 0) -> str:
    return json.dumps(
        {
            "steps": [
                {
                    "tool": tool,
                    "parameters": {"value": "x"},
                    "validation": {"metadata_equals": {"verified": True}},
                    "retry_count": retry_count,
                }
            ]
        }
    )


async def test_full_goal_plan_action_observation_validation_loop(tmp_path) -> None:
    provider = SequenceProvider(plan(), "concluído com evidência")
    tool = SchemaTool()
    registry = make_registry(tmp_path, tool)
    planner = TaskPlanner(provider, registry, AgentRouter(provider))
    response = await planner.run("tarefa complexa de teste", {})
    assert response == "concluído com evidência"
    assert tool.calls == 1
    assert provider.prompts[0]["phase"] == "GOAL_TO_PLAN"
    assert provider.prompts[1]["status"] == "completed"
    assert provider.prompts[1]["observations"][0]["validated"] is True


async def test_safe_retry_is_bounded_and_sensitive_action_never_auto_retries(tmp_path) -> None:
    failed = ToolResult(False, error="temporary")
    succeeded = ToolResult(True, output="done", metadata={"verified": True})
    safe = SchemaTool([failed, succeeded])
    safe_provider = SequenceProvider(plan(retry_count=1), "ok")
    safe_planner = TaskPlanner(safe_provider, make_registry(tmp_path / "safe", safe), AgentRouter(safe_provider))
    await safe_planner.run("tarefa complexa", {})
    assert safe.calls == 2

    sensitive = SensitiveSchemaTool([failed, succeeded])
    sensitive_provider = SequenceProvider(plan("sensitive_action", 1), "stopped")
    sensitive_planner = TaskPlanner(
        sensitive_provider,
        make_registry(tmp_path / "sensitive", sensitive),
        AgentRouter(sensitive_provider),
    )
    await sensitive_planner.run("tarefa complexa", {})
    assert sensitive.calls == 1
    assert sensitive_provider.prompts[-1]["status"] == "stopped"


@pytest.mark.parametrize(
    "malicious",
    [
        '{"tool":"schema_action","parameters":{"value":"x"}}',
        '{"steps":[{"tool":"unknown","parameters":{},"validation":{"output_contains":"x"}}]}',
        '{"steps":[{"tool":"schema_action","parameters":{"value":"x"},"validation":{}}]}',
        '{"steps":[{"tool":"schema_action","parameters":{"value":"x"},"validation":{"output_contains":""}}]}',
        '{"steps":[{"tool":"schema_action","parameters":{"value":"x"},"validation":{"metadata_equals":{}}}]}',
        '{"steps":[]}',
    ],
)
async def test_llm_cannot_call_tools_directly_or_bypass_contract(tmp_path, malicious) -> None:
    provider = SequenceProvider(malicious)
    tool = SchemaTool()
    planner = TaskPlanner(provider, make_registry(tmp_path, tool), AgentRouter(provider))
    with pytest.raises(PlanRejected):
        await planner.create_plan("tarefa complexa", {})
    assert tool.calls == 0


async def test_validation_failure_stops_following_steps(tmp_path) -> None:
    provider = SequenceProvider(
        json.dumps(
            {
                "steps": [
                    {
                        "tool": "schema_action",
                        "parameters": {"value": "first"},
                        "validation": {"output_contains": "missing"},
                    },
                    {
                        "tool": "schema_action",
                        "parameters": {"value": "second"},
                        "validation": {"output_contains": "done"},
                    },
                ]
            }
        ),
        "stopped",
    )
    tool = SchemaTool([ToolResult(True, output="done"), ToolResult(True, output="done")])
    planner = TaskPlanner(provider, make_registry(tmp_path, tool), AgentRouter(provider))
    await planner.run("tarefa complexa", {})
    assert tool.calls == 1
    assert provider.prompts[-1]["status"] == "stopped"


async def test_agent_core_complex_execution_is_disabled_by_default(tmp_path) -> None:
    provider = SequenceProvider("unused")
    registry = make_registry(tmp_path, SchemaTool())
    context = ContextManager(lambda: ScreenContext(), MemoryEngine(tmp_path / "memory.db"))
    core = AgentCore(registry, provider, context)
    response = await core.handle("Esta é uma tarefa complexa")
    assert response == "O planejamento com execução está desativado por segurança."
    assert provider.prompts == []
