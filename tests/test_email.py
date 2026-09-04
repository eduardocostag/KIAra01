import pytest

from app.integrations.email import DraftStore, EmailService
from app.tools.email import DraftEmailTool, SendEmailTool


class FakeProvider:
    async def send(self, draft):
        return f"sent:{draft.id}"


@pytest.mark.asyncio
async def test_email_requires_draft_and_cannot_replay(tmp_path):
    service = EmailService(DraftStore(tmp_path / "email.db"), FakeProvider())
    draft = service.draft("user@example.com", "Teste", "Corpo")
    assert (await service.send(draft.id)).startswith("sent:")
    with pytest.raises(ValueError):
        await service.send(draft.id)


def test_email_validates_recipient(tmp_path):
    service = EmailService(DraftStore(tmp_path / "email.db"))
    with pytest.raises(ValueError):
        service.draft("invalid", "subject", "body")


def test_email_tool_contracts_and_private_audit(tmp_path) -> None:
    service = EmailService(DraftStore(tmp_path / "email.db"))
    draft_tool = DraftEmailTool(service)
    send_tool = SendEmailTool(service)
    assert draft_tool.schema["required"] == ["to", "subject", "body"]
    assert send_tool.plannable is False
    audit = draft_tool.audit_parameters(
        {"to": "pessoa@example.com", "subject": "Assunto privado", "body": "Segredo"}
    )
    assert audit["recipient_domain"] == "example.com"
    assert "pessoa" not in str(audit)
    assert "Segredo" not in str(audit)
