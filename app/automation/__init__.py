"""Persistent scheduled and event-driven automations."""

from app.automation.catalog import AutomationTeacher, automation_template
from app.automation.engine import (
    AutomationEngine,
    AutomationSpec,
    AutomationStore,
    RunState,
    TriggerKind,
)

__all__ = ["AutomationEngine", "AutomationSpec", "AutomationStore", "AutomationTeacher", "RunState", "TriggerKind", "automation_template"]
