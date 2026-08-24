from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.automation.engine import AutomationSpec, TriggerKind

TEMPLATES: dict[str, AutomationSpec] = {
    "abrir_portal_diariamente": AutomationSpec(
        "Abrir portal diariamente", TriggerKind.RECURRING, "open_url",
        {"url": "https://example.com"}, interval_seconds=86400, enabled=False,
    ),
    "avisar_erro_detectado": AutomationSpec(
        "Registrar tela quando um erro for detectado", TriggerKind.EVENT, "take_screenshot", {},
        trigger_value="ERROR_DETECTED", enabled=False,
    ),
}


def automation_template(name: str, **parameter_overrides: Any) -> AutomationSpec:
    """Return an independent, disabled draft that must be reviewed before activation."""
    if name not in TEMPLATES:
        raise KeyError(name)
    source = TEMPLATES[name]
    return replace(source, id="", action_parameters={**source.action_parameters, **parameter_overrides}, enabled=False)


class AutomationTeacher:
    """Turns one explicit tool action into a disabled, review-only automation draft."""

    def prepare(self, *, name: str, action: str, parameters: dict[str, Any], trigger_event: str = "USER_REQUESTED") -> AutomationSpec:
        return AutomationSpec(name, TriggerKind.EVENT, action, dict(parameters), trigger_value=trigger_event, enabled=False)
