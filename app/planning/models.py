from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class LoopPhase(StrEnum):
    GOAL = "goal"
    PLAN = "plan"
    ACTION = "action"
    OBSERVATION = "observation"
    VALIDATION = "validation"


@dataclass(frozen=True, slots=True)
class PlanStep:
    tool: str
    parameters: dict[str, Any]
    validation: dict[str, Any]
    retry_count: int = 0


@dataclass(frozen=True, slots=True)
class TaskPlan:
    goal: str
    steps: tuple[PlanStep, ...]
    specialists: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StepObservation:
    step: int
    tool: str
    success: bool
    output: str
    error: str | None
    attempts: int
    validated: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class GoalStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class PersistentGoal:
    id: int
    goal: str
    plan: TaskPlan
    status: GoalStatus
    next_step: int
    risk: str
    estimated_cost: float
    estimated_duration_seconds: int
    created_at: datetime
    updated_at: datetime
