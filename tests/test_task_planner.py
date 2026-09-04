from __future__ import annotations

import json
from typing import Any, ClassVar

import pytest

from app.agents.router import AgentRouter
from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.memory import MemoryEngine
from app.models import AutonomyMode, PermissionLevel, ScreenContext, ToolResult
from app.planning import (
    GoalStatus,
    PlanRejected,
    PlanStep,
    PlanStore,
    TaskPlan,
    TaskPlanner,
)
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


class CriticalSchemaTool(SchemaTool):
    name = "critical_action"
    permission_level = PermissionLevel.CRITICAL_ACTION


class VisualSchemaTool(SchemaTool):
    name = "uia_click"
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


async def test_run_persists_checkpoints_and_completion_when_store_exists(tmp_path) -> None:
    provider = SequenceProvider(plan(), "concluÃ­do com checkpoint")
    tool = SchemaTool()
    store = PlanStore(tmp_path / "planning.db")
    planner = TaskPlanner(
        provider,
        make_registry(tmp_path, tool),
        AgentRouter(provider),
        store=store,
    )

    response = await planner.run("objetivo persistente", {})
    goal = store.get(1)

    assert response == "concluÃ­do com checkpoint"
    assert goal is not None
    assert goal.status is GoalStatus.COMPLETED
    assert goal.next_step == 1
    assert provider.prompts[-1]["goal_id"] == 1


async def test_critical_action_is_classified_as_high_risk(tmp_path) -> None:
    provider = SequenceProvider(plan("critical_action"))
    store = PlanStore(tmp_path / "planning.db")
    planner = TaskPlanner(
        provider,
        make_registry(tmp_path, CriticalSchemaTool()),
        AgentRouter(provider),
        store=store,
    )

    identifier = await planner.create_persistent_goal("mensagem externa", {})

    assert store.get(identifier).risk == "high"  # type: ignore[union-attr]


async def test_visual_operator_rejects_ui_plan_without_before_after_evidence(
    tmp_path,
) -> None:
    provider = SequenceProvider(plan("uia_click"))
    planner = TaskPlanner(
        provider,
        make_registry(tmp_path, VisualSchemaTool()),
        AgentRouter(provider),
        require_visual_validation=True,
    )

    with pytest.raises(PlanRejected, match="visual-change evidence"):
        await planner.create_plan("clique e confirme visualmente", {})


async def test_visual_operator_accepts_and_checks_complete_visual_evidence(
    tmp_path,
) -> None:
    visual_result = ToolResult(
        True,
        output="Post-condition verified",
        metadata={
            "verified": True,
            "visual_validation_available": True,
            "visual_changed": True,
        },
    )
    raw_plan = json.dumps(
        {
            "steps": [
                {
                    "tool": "uia_click",
                    "parameters": {"value": "x"},
                    "validation": {
                        "metadata_equals": {
                            "verified": True,
                            "visual_validation_available": True,
                            "visual_changed": True,
                        }
                    },
                }
            ]
        }
    )
    provider = SequenceProvider(raw_plan, "mudanca visual confirmada")
    tool = VisualSchemaTool([visual_result])
    planner = TaskPlanner(
        provider,
        make_registry(tmp_path, tool),
        AgentRouter(provider),
        require_visual_validation=True,
    )

    response = await planner.run("clique e confirme visualmente", {})

    assert response == "mudanca visual confirmada"
    assert provider.prompts[-1]["observations"][0]["validated"] is True


async def test_failure_creates_different_recovery_plan_without_executing_it(
    tmp_path,
) -> None:
    recovery_plan = json.dumps(
        {
            "steps": [
                {
                    "tool": "schema_action",
                    "parameters": {"value": "alternative"},
                    "validation": {"metadata_equals": {"verified": True}},
                }
            ]
        }
    )
    provider = SequenceProvider(plan(), recovery_plan, "primeira tentativa interrompida")
    tool = SchemaTool([ToolResult(False, error="falhou")])
    store = PlanStore(tmp_path / "planning.db")
    planner = TaskPlanner(
        provider,
        make_registry(tmp_path, tool),
        AgentRouter(provider),
        store=store,
        recovery_on_failure=True,
    )

    response = await planner.run("objetivo com recuperacao", {})
    original = store.get(1)
    recovery = store.get(2)

    assert original is not None and original.status is GoalStatus.STOPPED
    assert recovery is not None and recovery.status is GoalStatus.PENDING
    assert recovery.plan.steps[0].parameters == {"value": "alternative"}
    assert tool.calls == 1
    assert "Plano de recuperação 2 criado" in response
    assert provider.prompts[1]["context"]["recovery_evidence"]["failed_observation"]


async def test_recovery_plan_cannot_repeat_identical_failed_action(tmp_path) -> None:
    provider = SequenceProvider(plan(), plan(), "sem alternativa segura")
    tool = SchemaTool([ToolResult(False, error="falhou")])
    store = PlanStore(tmp_path / "planning.db")
    planner = TaskPlanner(
        provider,
        make_registry(tmp_path, tool),
        AgentRouter(provider),
        store=store,
        recovery_on_failure=True,
    )

    response = await planner.run("objetivo sem alternativa", {})

    assert store.get(2) is None
    assert "Plano de recuperação" not in response


async def test_explicit_resume_executes_pending_recovery_with_checkpoint(tmp_path) -> None:
    provider = SequenceProvider("recuperacao concluida")
    tool = SchemaTool()
    store = PlanStore(tmp_path / "planning.db")
    identifier = store.create(
        TaskPlan(
            "alternativa",
            (
                PlanStep(
                    "schema_action",
                    {"value": "alternative"},
                    {"metadata_equals": {"verified": True}},
                ),
            ),
        ),
        risk="medium",
    )
    planner = TaskPlanner(
        provider,
        make_registry(tmp_path, tool),
        AgentRouter(provider),
        store=store,
    )

    response = await planner.resume_goal(identifier)

    assert response == "recuperacao concluida"
    assert store.get(identifier).status is GoalStatus.COMPLETED  # type: ignore[union-attr]
    assert tool.calls == 1


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
