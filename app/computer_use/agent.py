from __future__ import annotations

import asyncio
from typing import Protocol

from app.computer_use.backend import AutomationBackend
from app.computer_use.models import (
    ElementSelector,
    PostCondition,
    PostConditionKind,
    WindowOperation,
    WindowSelector,
)
from app.models import ToolResult


class VisionFallback(Protocol):
    async def resolve(
        self, window: WindowSelector, requested: ElementSelector
    ) -> ElementSelector | None: ...


class VisualStateVerifier(Protocol):
    async def signature(self) -> str | None: ...


class ComputerUseAgent:
    """Structured UIA-first computer use; vision may only refine semantic selectors."""

    def __init__(
        self,
        backend: AutomationBackend,
        *,
        vision_fallback: VisionFallback | None = None,
        allow_vision_fallback: bool = False,
        operation_timeout_seconds: float = 5.0,
        visual_state_verifier: VisualStateVerifier | None = None,
        require_visual_validation: bool = False,
        visual_settle_seconds: float = 0.0,
    ) -> None:
        self.backend = backend
        self.vision_fallback = vision_fallback
        self.allow_vision_fallback = allow_vision_fallback
        self.operation_timeout_seconds = max(0.5, operation_timeout_seconds)
        self.visual_state_verifier = visual_state_verifier
        self.require_visual_validation = require_visual_validation
        self.visual_settle_seconds = min(2.0, max(0.0, visual_settle_seconds))

    async def _backend(self, function, *args, **kwargs):
        return await asyncio.wait_for(
            asyncio.to_thread(function, *args, **kwargs),
            timeout=self.operation_timeout_seconds,
        )

    async def locate(
        self, window: WindowSelector, element: ElementSelector | None = None
    ) -> tuple[object, object | None]:
        window.validate()
        target_window = await self._backend(self.backend.find_window, window)
        if target_window is None:
            raise LookupError("Window not found")
        if element is None:
            return target_window, None
        element.validate()
        target = await self._backend(self.backend.find_element, target_window, element)
        if target is None and self.allow_vision_fallback and self.vision_fallback is not None:
            refined = await self.vision_fallback.resolve(window, element)
            if refined is not None:
                refined.validate()
                target = await self._backend(self.backend.find_element, target_window, refined)
        if target is None:
            raise LookupError("UI Automation element not found")
        return target_window, target

    async def click(
        self, window: WindowSelector, element: ElementSelector, post: PostCondition
    ) -> ToolResult:
        before = await self._visual_signature()
        target_window, target = await self.locate(window, element)
        await self._backend(self.backend.click, target)
        return await self._verify(target_window, target, post, before)

    async def type_text(
        self,
        window: WindowSelector,
        element: ElementSelector,
        text: str,
        *,
        replace: bool,
        post: PostCondition,
    ) -> ToolResult:
        before = await self._visual_signature()
        _, target = await self.locate(window, element)
        await self._backend(self.backend.type_text, target, text, replace=replace)
        return await self._verify(_, target, post, before)

    async def send_key(
        self, window: WindowSelector, element: ElementSelector | None, key: str, post: PostCondition
    ) -> ToolResult:
        before = await self._visual_signature()
        target_window, target = await self.locate(window, element)
        await self._backend(self.backend.send_key, target or target_window, key)
        return await self._verify(target_window, target or target_window, post, before)

    async def operate_window(
        self, window: WindowSelector, operation: WindowOperation, post: PostCondition
    ) -> ToolResult:
        before = await self._visual_signature()
        target_window, _ = await self.locate(window)
        await self._backend(self.backend.window_operation, target_window, operation)
        return await self._verify(target_window, target_window, post, before)

    async def _verify(
        self, window: object, target: object, post: PostCondition, before: str | None = None
    ) -> ToolResult:
        if post.kind == PostConditionKind.EXISTS:
            passed = await self._backend(self.backend.exists, target)
        elif post.kind == PostConditionKind.NOT_EXISTS:
            passed = not await self._backend(self.backend.exists, target)
        elif post.kind == PostConditionKind.FOCUSED:
            passed = await self._backend(self.backend.focused, target)
        elif post.kind == PostConditionKind.VALUE_EQUALS:
            passed = await self._backend(self.backend.value, target) == (post.expected or "")
        else:
            title = await self._backend(self.backend.window_title, window)
            passed = (post.expected or "").casefold() in title.casefold()
        if self.visual_state_verifier is not None and self.visual_settle_seconds:
            await asyncio.sleep(self.visual_settle_seconds)
        after = await self._visual_signature()
        visual_available = before is not None and after is not None
        visual_changed = self._visual_changed(before, after)
        verified = passed
        status = "failed_post_condition"
        error = None if passed else f"Post-condition failed: {post.kind.value}"
        if passed and self.require_visual_validation and not visual_available:
            verified = False
            status = "inconclusive_visual_unavailable"
            error = "Visual validation unavailable; action result is inconclusive"
        elif passed and self.require_visual_validation and not visual_changed:
            verified = False
            status = "inconclusive_no_visual_change"
            error = "No material visual change observed; action result is inconclusive"
        elif passed and visual_available and visual_changed:
            status = "confirmed_post_condition_and_visual_change"
        elif passed:
            status = "confirmed_post_condition"
        return ToolResult(
            verified,
            output="Post-condition verified" if verified else "",
            error=error,
            metadata={
                "post_condition": post.kind.value,
                "post_condition_passed": passed,
                "verified": verified,
                "verification_status": status,
                "visual_validation_required": self.require_visual_validation,
                "visual_validation_available": visual_available,
                "visual_changed": visual_changed,
            },
        )

    def _visual_changed(self, before: str | None, after: str | None) -> bool:
        if before is None or after is None:
            return False
        comparator = getattr(self.visual_state_verifier, "changed", None)
        if callable(comparator):
            return bool(comparator(before, after))
        return before != after

    async def _visual_signature(self) -> str | None:
        if self.visual_state_verifier is None:
            return None
        try:
            return await self.visual_state_verifier.signature()
        except (RuntimeError, OSError, ValueError):
            return None
