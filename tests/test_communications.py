from __future__ import annotations

import pytest

from app.integrations.communications import MicrosoftGraphCommunications, OutboundMessage
from app.integrations.credentials import ChainedCredentials
from app.integrations.email import DraftEmail, GmailEmailProvider
from app.integrations.http import HttpResponse


class Credentials:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, name):
        return self.values.get(name)


class FakeHttp:
    def __init__(self):
        self.calls = []

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if "messages/send" in url:
            return HttpResponse(200, {"id": "gmail-1"})
        if url.endswith("/messages") and method == "POST":
            return HttpResponse(201, {"id": "message-1"})
        return HttpResponse(200, {"value": [{"id": "read-1"}]})


def test_chained_credentials_does_not_require_persisted_config():
    credentials = ChainedCredentials(Credentials(), Credentials({"TOKEN": "secret"}))
    assert credentials.get("TOKEN") == "secret"


@pytest.mark.asyncio
async def test_graph_message_passes_idempotency_key():
    http = FakeHttp()
    graph = MicrosoftGraphCommunications(Credentials({"KIARA_GRAPH_TOKEN": "token"}), http)
    message = OutboundMessage.prepare("chat-id", "Olá")
    assert await graph.send_message(message) == "message-1"
    assert http.calls[0][2]["idempotency_key"] == message.idempotency_key


@pytest.mark.asyncio
async def test_graph_reads_without_mutation():
    http = FakeHttp()
    graph = MicrosoftGraphCommunications(Credentials({"KIARA_GRAPH_TOKEN": "token"}), http)
    assert await graph.read_calendar() == [{"id": "read-1"}]
    assert http.calls[0][0] == "GET"


@pytest.mark.asyncio
async def test_gmail_builds_real_api_request_offline():
    http = FakeHttp()
    gmail = GmailEmailProvider(Credentials({"KIARA_GMAIL_TOKEN": "token"}), http)
    identifier = await gmail.send(DraftEmail("user@example.com", "Assunto", "Corpo", "draft-1"))
    assert identifier == "gmail-1"
    assert http.calls[0][2]["payload"]["raw"]


@pytest.mark.asyncio
async def test_missing_graph_credential_fails_before_network():
    http = FakeHttp()
    graph = MicrosoftGraphCommunications(Credentials(), http)
    with pytest.raises(RuntimeError, match="não configurada"):
        await graph.read_messages()
    assert http.calls == []
