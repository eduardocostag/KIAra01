import pytest

from app.models import AutonomyMode, PermissionLevel
from app.security.permissions import PermissionDenied, PermissionGate


def test_critical_action_requires_confirmation():
    gate = PermissionGate(AutonomyMode.AUTONOMOUS, confirm=lambda _: False)
    with pytest.raises(PermissionDenied):
        gate.authorize(PermissionLevel.CRITICAL_ACTION, "delete")


def test_read_only_allowed_in_observe():
    assert PermissionGate(AutonomyMode.OBSERVE).authorize(PermissionLevel.READ_ONLY, "inspect")
