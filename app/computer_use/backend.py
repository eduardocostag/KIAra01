from __future__ import annotations

from typing import Any, Protocol

from app.computer_use.models import ElementSelector, WindowOperation, WindowSelector


class AutomationBackend(Protocol):
    def find_window(self, selector: WindowSelector) -> Any | None: ...
    def find_element(self, window: Any, selector: ElementSelector) -> Any | None: ...
    def click(self, element: Any) -> None: ...
    def type_text(self, element: Any, text: str, *, replace: bool) -> None: ...
    def send_key(self, target: Any, key: str) -> None: ...
    def window_operation(self, window: Any, operation: WindowOperation) -> None: ...
    def exists(self, target: Any) -> bool: ...
    def focused(self, target: Any) -> bool: ...
    def value(self, target: Any) -> str: ...
    def window_title(self, window: Any) -> str: ...


class PywinautoBackend:
    """Optional Windows UIA adapter. Importing this module never requires pywinauto."""

    @staticmethod
    def _desktop():
        try:
            from pywinauto import Desktop
        except ImportError as exc:
            raise RuntimeError("Install the 'perception' extra for Windows UI Automation") from exc
        return Desktop(backend="uia")

    def find_window(self, selector: WindowSelector):
        if selector.process and selector.process.isdigit():
            try:
                from pywinauto import Application

                app = Application(backend="uia").connect(process=int(selector.process), timeout=1)
                window = app.top_window()
                if selector.title and window.window_text() != selector.title:
                    return None
                if selector.class_name and window.class_name() != selector.class_name:
                    return None
                return window
            except (ImportError, RuntimeError, TimeoutError):
                return None
        criteria: dict[str, Any] = {}
        if selector.title:
            criteria["title"] = selector.title
        if selector.process:
            criteria["process"] = (
                int(selector.process) if selector.process.isdigit() else selector.process
            )
        if selector.class_name:
            criteria["class_name"] = selector.class_name
        window = self._desktop().window(**criteria)
        return window if window.exists(timeout=0.5) else None

    def find_element(self, window, selector: ElementSelector):
        criteria = {
            key: value
            for key, value in {
                "auto_id": selector.automation_id,
                "title": selector.name,
                "control_type": selector.control_type,
                "class_name": selector.class_name,
            }.items()
            if value
        }
        element = window.child_window(**criteria)
        return element if element.exists(timeout=0.5) else None

    def click(self, element) -> None:
        element.wrapper_object().click_input()

    def type_text(self, element, text: str, *, replace: bool) -> None:
        wrapper = element.wrapper_object()
        wrapper.set_focus()
        if replace:
            wrapper.type_keys("^a", set_foreground=True)
        wrapper.type_keys(text, with_spaces=True, set_foreground=True)

    def send_key(self, target, key: str) -> None:
        target.wrapper_object().type_keys(key, set_foreground=True)

    def window_operation(self, window, operation: WindowOperation) -> None:
        wrapper = window.wrapper_object()
        getattr(
            wrapper, operation.value
        )() if operation != WindowOperation.FOCUS else wrapper.set_focus()

    def exists(self, target) -> bool:
        return bool(target.exists(timeout=0.2))

    def focused(self, target) -> bool:
        return bool(target.wrapper_object().has_keyboard_focus())

    def value(self, target) -> str:
        wrapper = target.wrapper_object()
        try:
            return str(wrapper.get_value())
        except AttributeError:
            return str(wrapper.window_text())

    def window_title(self, window) -> str:
        return str(window.wrapper_object().window_text())
