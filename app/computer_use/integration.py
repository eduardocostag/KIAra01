from __future__ import annotations

from app.computer_use.agent import ComputerUseAgent, VisionFallback, VisualStateVerifier
from app.computer_use.backend import AutomationBackend, PywinautoBackend
from app.computer_use.tools import (
    UiaClickTool,
    UiaKeyTool,
    UiaLocateTool,
    UiaTypeTextTool,
    UiaWindowTool,
)
from app.config import Settings
from app.tools.registry import ToolRegistry


def register_computer_use_tools(
    registry: ToolRegistry,
    settings: Settings,
    *,
    backend: AutomationBackend | None = None,
    vision_fallback: VisionFallback | None = None,
    visual_state_verifier: VisualStateVerifier | None = None,
) -> ComputerUseAgent | None:
    """Conditionally expose privileged desktop verbs from explicit configuration."""
    if not settings.get("computer_use.enabled", False):
        return None
    agent = ComputerUseAgent(
        backend or PywinautoBackend(),
        vision_fallback=vision_fallback,
        allow_vision_fallback=bool(
            settings.get("computer_use.vision_fallback_enabled", False)
        ),
        operation_timeout_seconds=float(
            settings.get("computer_use.operation_timeout_seconds", 5.0)
        ),
        visual_state_verifier=visual_state_verifier,
    )
    for tool_type in (UiaLocateTool, UiaClickTool, UiaTypeTextTool, UiaKeyTool, UiaWindowTool):
        registry.register(tool_type(agent))
    return agent
