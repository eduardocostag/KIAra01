from __future__ import annotations

import pytest

from app.computer_use import (
    ComputerUseAgent,
    ElementSelector,
    PostCondition,
    PostConditionKind,
    UiaClickTool,
    UiaKeyTool,
    UiaLocateTool,
    UiaTypeTextTool,
    WindowSelector,
)
from app.computer_use.visual_validation import EphemeralVisualStateVerifier
from app.models import PermissionLevel


class FakeBackend:
    def __init__(self) -> None:
        self.window = {"title": "Editor", "focused": True, "exists": True}
        self.element = {"value": "", "focused": True, "exists": True}
        self.calls = []

    def find_window(self, selector):
        self.calls.append(("find_window", selector))
        return self.window

    def find_element(self, window, selector):
        self.calls.append(("find_element", selector))
        return self.element if selector.automation_id != "missing" else None

    def click(self, element):
        self.calls.append(("click", element))

    def type_text(self, element, text, *, replace):
        self.calls.append(("type", text, replace))
        element["value"] = text if replace else element["value"] + text

    def send_key(self, target, key):
        self.calls.append(("key", key))

    def window_operation(self, window, operation):
        self.calls.append(("window", operation))

    def exists(self, target):
        return target["exists"]

    def focused(self, target):
        return target["focused"]

    def value(self, target):
        return target["value"]

    def window_title(self, window):
        return window["title"]


async def test_uia_first_click_and_post_condition_without_coordinates() -> None:
    backend = FakeBackend()
    agent = ComputerUseAgent(backend)
    result = await agent.click(
        WindowSelector(title="Editor"),
        ElementSelector(automation_id="save"),
        PostCondition(PostConditionKind.EXISTS),
    )
    assert result.success is True
    assert [call[0] for call in backend.calls] == ["find_window", "find_element", "click"]


async def test_action_records_ephemeral_before_after_visual_validation() -> None:
    class Verifier:
        def __init__(self):
            self.states = iter(["before-hash", "after-hash"])

        async def signature(self):
            return next(self.states)

    result = await ComputerUseAgent(FakeBackend(), visual_state_verifier=Verifier()).click(
        WindowSelector(title="Editor"),
        ElementSelector(name="Save"),
        PostCondition(PostConditionKind.EXISTS),
    )
    assert result.metadata["visual_validation_available"] is True
    assert result.metadata["visual_changed"] is True
    assert "before-hash" not in result.metadata


async def test_required_visual_validation_marks_unavailable_evidence_inconclusive() -> None:
    result = await ComputerUseAgent(FakeBackend(), require_visual_validation=True).click(
        WindowSelector(title="Editor"),
        ElementSelector(name="Save"),
        PostCondition(PostConditionKind.EXISTS),
    )
    assert result.success is False
    assert result.metadata["post_condition_passed"] is True
    assert result.metadata["verification_status"] == "inconclusive_visual_unavailable"


async def test_required_visual_validation_rejects_unchanged_screen() -> None:
    class UnchangedVerifier:
        async def signature(self):
            return "same"

    result = await ComputerUseAgent(
        FakeBackend(),
        visual_state_verifier=UnchangedVerifier(),
        require_visual_validation=True,
    ).click(
        WindowSelector(title="Editor"),
        ElementSelector(name="Save"),
        PostCondition(PostConditionKind.EXISTS),
    )
    assert result.success is False
    assert result.metadata["verification_status"] == "inconclusive_no_visual_change"


async def test_required_visual_validation_confirms_changed_screen() -> None:
    class ChangedVerifier:
        def __init__(self):
            self.states = iter(["before", "after"])

        async def signature(self):
            return next(self.states)

    result = await ComputerUseAgent(
        FakeBackend(),
        visual_state_verifier=ChangedVerifier(),
        require_visual_validation=True,
    ).click(
        WindowSelector(title="Editor"),
        ElementSelector(name="Save"),
        PostCondition(PostConditionKind.EXISTS),
    )
    assert result.success is True
    assert result.metadata["verification_status"] == ("confirmed_post_condition_and_visual_change")


def test_visual_change_threshold_ignores_tiny_screen_noise() -> None:
    verifier = EphemeralVisualStateVerifier(  # type: ignore[arg-type]
        object(), change_threshold=0.02
    )
    before = bytes([0] * 256).hex()
    one_changed_bit = bytes([1, *([0] * 255)]).hex()
    six_changed_bits = bytes([1] * 6 + [0] * 250).hex()

    assert verifier.changed(before, one_changed_bit) is False
    assert verifier.changed(before, six_changed_bits) is True


async def test_type_requires_verified_result() -> None:
    backend = FakeBackend()
    agent = ComputerUseAgent(backend)
    result = await agent.type_text(
        WindowSelector(title="Editor"),
        ElementSelector(name="Body"),
        "Olá",
        replace=True,
        post=PostCondition(PostConditionKind.VALUE_EQUALS, "Olá"),
    )
    assert result.success is True
    assert result.metadata["verified"] is True


async def test_failed_post_condition_is_reported() -> None:
    backend = FakeBackend()
    result = await ComputerUseAgent(backend).click(
        WindowSelector(title="Editor"),
        ElementSelector(name="Save"),
        PostCondition(PostConditionKind.WINDOW_TITLE_CONTAINS, "Browser"),
    )
    assert result.success is False
    assert result.error == "Post-condition failed: window_title_contains"


class FakeVision:
    def __init__(self) -> None:
        self.calls = 0

    async def resolve(self, window, requested):
        self.calls += 1
        return ElementSelector(automation_id="resolved")


async def test_vision_is_opt_in_fallback_and_returns_selector_not_coordinates() -> None:
    backend = FakeBackend()
    vision = FakeVision()
    agent = ComputerUseAgent(backend, vision_fallback=vision, allow_vision_fallback=True)
    _, target = await agent.locate(
        WindowSelector(title="Editor"), ElementSelector(automation_id="missing")
    )
    assert target is backend.element
    assert vision.calls == 1


def test_tools_validate_schema_text_limit_and_key_allowlist() -> None:
    agent = ComputerUseAgent(FakeBackend())
    common = {
        "window": {"title": "Editor"},
        "element": {"name": "Body"},
        "post_condition": {"kind": "exists"},
    }
    UiaClickTool(agent).validate(common)
    with pytest.raises(ValueError, match="at most"):
        UiaTypeTextTool(agent).validate({**common, "text": "x" * 10_001})
    with pytest.raises(ValueError, match="allowlisted"):
        UiaKeyTool(agent).validate({**common, "key": "^%DELETE"})
    with pytest.raises(ValueError, match="unknown"):
        UiaClickTool(agent).validate({**common, "x": 10})
    assert UiaClickTool(agent).permission_level == PermissionLevel.SENSITIVE_ACTION


async def test_locate_tool_is_read_only_and_returns_no_native_handle() -> None:
    tool = UiaLocateTool(ComputerUseAgent(FakeBackend()))
    parameters = {"window": {"title": "Editor"}, "element": {"automation_id": "save"}}
    tool.validate(parameters)
    result = await tool.execute(**parameters)
    assert result.success is True
    assert result.metadata == {"window_found": True, "element_found": True}
    assert "handle" not in result.metadata
