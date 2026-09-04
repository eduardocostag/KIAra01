from __future__ import annotations

import pytest

from app.leads import ProspectingPolicy, ProspectingPolicyEngine, SuppressionStore
from app.models import AutonomyMode
from app.security.audit import AuditLog
from app.security.kill_switch import KillSwitch
from app.security.permissions import PermissionGate
from app.tools.registry import ToolRegistry
from app.tools.social import SendSocialMessageTool


class FakeBrowser:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def send_social_message(
        self, *, platform: str, recipient: str, message: str
    ) -> str:
        self.calls.append(
            {"platform": platform, "recipient": recipient, "message": message}
        )
        return "enviada"


@pytest.mark.asyncio
async def test_social_send_requires_confirmation_and_redacts_message(tmp_path) -> None:
    decisions = iter((False, True))
    prompts: list[str] = []

    def confirm(summary: str) -> bool:
        prompts.append(summary)
        return next(decisions)

    browser = FakeBrowser()
    registry = ToolRegistry(
        PermissionGate(AutonomyMode.EXECUTE_WITH_CONFIRMATION, confirm),
        AuditLog(tmp_path / "audit.jsonl"),
        KillSwitch(),
    )
    registry.register(SendSocialMessageTool(browser))  # type: ignore[arg-type]

    denied = await registry.execute(
        "send_social_message",
        platform="instagram",
        recipient="@maria",
        text="mensagem privada",
    )
    sent = await registry.execute(
        "send_social_message",
        platform="instagram",
        recipient="@maria",
        text="mensagem privada",
    )

    assert denied.success is False
    assert sent.success is True
    assert browser.calls == [
        {"platform": "instagram", "recipient": "@maria", "message": "mensagem privada"}
    ]
    assert all("mensagem privada" not in prompt for prompt in prompts)
    assert all("[REDACTED]" in prompt for prompt in prompts)


@pytest.mark.parametrize(
    "parameters",
    (
        {"platform": "email", "recipient": "maria", "text": "oi"},
        {"platform": "telegram", "recipient": "?", "text": "oi"},
        {"platform": "whatsapp", "recipient": "+5511999999999", "text": ""},
    ),
)
def test_social_tool_rejects_unsafe_or_incomplete_parameters(parameters) -> None:
    tool = SendSocialMessageTool(FakeBrowser())  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        tool.validate(parameters)


@pytest.mark.asyncio
async def test_social_tool_enforces_opt_out_before_browser_delivery(tmp_path) -> None:
    policy_path = tmp_path / "policy.db"
    suppressions = SuppressionStore(policy_path)
    suppressions.suppress("+5511999999999")
    suppressions.close()
    engine = ProspectingPolicyEngine(policy_path, ProspectingPolicy(daily_limit=5))
    browser = FakeBrowser()
    tool = SendSocialMessageTool(browser, engine)  # type: ignore[arg-type]

    result = await tool.execute(
        platform="whatsapp", recipient="+5511999999999", text="Olá"
    )

    assert result.success is False
    assert browser.calls == []
    engine.close()
