from __future__ import annotations

from collections.abc import Callable

from app.models import AutonomyMode, PermissionLevel


class PermissionDenied(RuntimeError):
    pass


class PermissionGate:
    def __init__(self, mode: AutonomyMode, confirm: Callable[[str], bool] | None = None) -> None:
        self.mode = mode
        self.confirm = confirm

    def authorize(self, level: PermissionLevel, summary: str) -> bool:
        if self.mode == AutonomyMode.OBSERVE and level != PermissionLevel.READ_ONLY:
            raise PermissionDenied("Modo OBSERVE impede ações.")
        if self.mode == AutonomyMode.ASSIST and level != PermissionLevel.READ_ONLY:
            raise PermissionDenied("Modo ASSIST apenas sugere ações.")
        needs_confirmation = level in {PermissionLevel.SENSITIVE_ACTION, PermissionLevel.CRITICAL_ACTION}
        if needs_confirmation and (self.confirm is None or not self.confirm(summary)):
            raise PermissionDenied("Ação não confirmada pelo usuário.")
        return True
