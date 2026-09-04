from __future__ import annotations

from typing import Any, ClassVar

from app.computer_use.agent import ComputerUseAgent
from app.computer_use.models import (
    ElementSelector,
    PostCondition,
    PostConditionKind,
    WindowOperation,
    WindowSelector,
)
from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool


def _window(raw: dict[str, Any]) -> WindowSelector:
    return WindowSelector(**raw)


def _element(raw: dict[str, Any] | None) -> ElementSelector | None:
    return ElementSelector(**raw) if raw is not None else None


def _post(raw: dict[str, Any]) -> PostCondition:
    return PostCondition(PostConditionKind(raw["kind"]), raw.get("expected"))


class ComputerUseTool(Tool):
    schema: ClassVar[dict[str, Any]]

    def __init__(self, agent: ComputerUseAgent) -> None:
        self.agent = agent

    def validate(self, parameters: dict[str, Any]) -> None:
        unknown = set(parameters) - set(self.schema["properties"])
        missing = set(self.schema.get("required", ())) - set(parameters)
        if unknown or missing:
            raise ValueError(
                f"Invalid parameters; missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        if not isinstance(parameters.get("window"), dict):
            raise TypeError("window must be an object")
        _window(parameters["window"]).validate()
        if "element" in parameters and parameters["element"] is not None:
            if not isinstance(parameters["element"], dict):
                raise ValueError("element must be an object")
            _element(parameters["element"]).validate()  # type: ignore[union-attr]
        if not isinstance(parameters.get("post_condition"), dict):
            raise TypeError("post_condition is required and must be an object")
        _post(parameters["post_condition"])


_COMMON = {
    "window": {"type": "object"},
    "element": {"type": "object"},
    "post_condition": {"type": "object"},
}


class UiaLocateTool(ComputerUseTool):
    name = "uia_locate"
    description = "Locate a window or element using UI Automation properties."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "properties": {"window": {"type": "object"}, "element": {"type": "object"}},
        "required": ["window"],
    }

    def validate(self, parameters: dict[str, Any]) -> None:
        unknown = set(parameters) - {"window", "element"}
        if unknown or "window" not in parameters:
            raise ValueError(f"Invalid locate parameters; unknown={sorted(unknown)}")
        if not isinstance(parameters["window"], dict):
            raise TypeError("window must be an object")
        _window(parameters["window"]).validate()
        if parameters.get("element") is not None:
            if not isinstance(parameters["element"], dict):
                raise TypeError("element must be an object")
            selector = _element(parameters["element"])
            assert selector is not None
            selector.validate()

    async def execute(self, **parameters: Any) -> ToolResult:
        window, element = await self.agent.locate(
            _window(parameters["window"]), _element(parameters.get("element"))
        )
        return ToolResult(
            True,
            output="UI Automation target found",
            metadata={"window_found": window is not None, "element_found": element is not None},
        )


class UiaClickTool(ComputerUseTool):
    name = "uia_click"
    description = "Click a UI Automation element selected by semantic properties."
    # A semantic selector can still target "Excluir", "Comprar" or "Enviar".
    permission_level = PermissionLevel.SENSITIVE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": _COMMON,
        "required": ["window", "element", "post_condition"],
    }

    async def execute(self, **parameters: Any) -> ToolResult:
        return await self.agent.click(
            _window(parameters["window"]),
            _element(parameters["element"]),
            _post(parameters["post_condition"]),  # type: ignore[arg-type]
        )


class UiaTypeTextTool(ComputerUseTool):
    name = "uia_type_text"
    description = "Type bounded text into a UI Automation element."
    permission_level = PermissionLevel.SENSITIVE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {**_COMMON, "text": {"type": "string"}, "replace": {"type": "boolean"}},
        "required": ["window", "element", "text", "post_condition"],
    }

    def validate(self, parameters: dict[str, Any]) -> None:
        super().validate(parameters)
        if not isinstance(parameters["text"], str) or len(parameters["text"]) > 10_000:
            raise ValueError("text must be a string of at most 10000 characters")
        if "replace" in parameters and not isinstance(parameters["replace"], bool):
            raise ValueError("replace must be boolean")

    async def execute(self, **parameters: Any) -> ToolResult:
        return await self.agent.type_text(
            _window(parameters["window"]),
            _element(parameters["element"]),
            parameters["text"],
            replace=parameters.get("replace", False),
            post=_post(parameters["post_condition"]),
        )  # type: ignore[arg-type]


class UiaKeyTool(ComputerUseTool):
    name = "uia_key"
    description = "Send an allowlisted navigation key to a located UIA target."
    permission_level = PermissionLevel.SENSITIVE_ACTION
    ALLOWED_KEYS: ClassVar[frozenset[str]] = frozenset(
        {"ENTER", "ESC", "TAB", "UP", "DOWN", "LEFT", "RIGHT", "HOME", "END"}
    )
    schema: ClassVar[dict[str, Any]] = {
        "properties": {**_COMMON, "key": {"type": "string"}},
        "required": ["window", "key", "post_condition"],
    }

    def validate(self, parameters: dict[str, Any]) -> None:
        super().validate(parameters)
        if parameters["key"].upper() not in self.ALLOWED_KEYS:
            raise ValueError("key is not allowlisted")

    async def execute(self, **parameters: Any) -> ToolResult:
        return await self.agent.send_key(
            _window(parameters["window"]),
            _element(parameters.get("element")),
            parameters["key"].upper(),
            _post(parameters["post_condition"]),
        )


class UiaWindowTool(ComputerUseTool):
    name = "uia_window"
    description = "Operate a located window without screen coordinates."
    permission_level = PermissionLevel.SENSITIVE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {**_COMMON, "operation": {"type": "string"}},
        "required": ["window", "operation", "post_condition"],
    }

    def validate(self, parameters: dict[str, Any]) -> None:
        super().validate(parameters)
        WindowOperation(parameters["operation"])

    async def execute(self, **parameters: Any) -> ToolResult:
        return await self.agent.operate_window(
            _window(parameters["window"]),
            WindowOperation(parameters["operation"]),
            _post(parameters["post_condition"]),
        )
