from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from kiara_api import chatwoot
from kiara_api.http.errors import ApiError
from kiara_api.integrations import IntegrationRepository, _validate_credentials
from kiara_api.ports.identity import IdentityPrincipal

HEADERS = {"Authorization": "Bearer org-a"}
CREDENTIALS = {"endpoint_url": "https://support.example.com",
               "api_access_token": "synthetic-chatwoot-token", "account_id": "4"}


class Repository:
    def __init__(self):
        self.reads = []

    async def credentials_for(self, organization_id, provider):
        self.reads.append((organization_id, provider))
        if organization_id == "org-a":
            return CREDENTIALS.copy()
        return None


class Adapter:
    def __init__(self):
        self.calls = []
        self.fail = False

    async def list_inboxes(self, **parameters):
        self.calls.append(("inboxes", parameters))
        return [{"id": 1, "name": "Customer support"}]

    async def list_conversations(self, **parameters):
        self.calls.append(("conversations", parameters))
        return [{"id": 5, "status": "open"}]

    async def list_messages(self, conversation_id, **parameters):
        self.calls.append(("messages", conversation_id, parameters))
        return [{"id": 6, "content": "hello"}]

    async def send_message(self, conversation_id, content):
        self.calls.append(("send", conversation_id, content))
        if self.fail:
            raise RuntimeError("Secret or provider payload must never be exposed")
        return {"id": 7, "message_type": "outgoing"}


def make_client(monkeypatch, role="owner"):
    app = FastAPI()
    repository, adapter = Repository(), Adapter()
    observed = []

    class Verifier:
        async def verify(self, token):
            if token not in {"org-a", "org-b"}:
                raise ApiError(401, "invalid_token", "Invalid token")
            return IdentityPrincipal("user-1", token, "membership-1", role)

    app.state.identity_verifier = Verifier()

    @app.middleware("http")
    async def correlation(request, call_next):
        request.state.correlation_id = "test-chatwoot"
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def error_handler(request, error):
        return JSONResponse({"code": error.code, "message": error.message}, status_code=error.status_code)

    def runtime(credentials):
        observed.append(credentials)
        return adapter

    monkeypatch.setattr(chatwoot, "_runtime_client", runtime)
    app.include_router(chatwoot.create_chatwoot_router(repository))
    return TestClient(app), repository, adapter, observed


@pytest.mark.parametrize("path", ["/v1/chatwoot/inboxes", "/v1/chatwoot/conversations",
                                 "/v1/chatwoot/conversations/5/messages"])
def test_all_reads_require_authentication(monkeypatch, path):
    client, repo, adapter, _ = make_client(monkeypatch)
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert repo.reads == []
    assert adapter.calls == []


def test_membership_selects_credentials_and_unconfigured_tenant_cannot_read_other(monkeypatch):
    client, repo, adapter, observed = make_client(monkeypatch)
    result = client.get("/v1/chatwoot/inboxes", headers=HEADERS)
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert observed == [CREDENTIALS]
    assert repo.reads == [("org-a", "chatwoot")]
    assert "synthetic" not in result.text
    second = client.get("/v1/chatwoot/inboxes", headers={"Authorization": "Bearer org-b"})
    assert second.status_code == 404
    assert len(adapter.calls) == 1


def test_read_options_are_bounded_and_forwarded(monkeypatch):
    client, _, adapter, _ = make_client(monkeypatch)
    result = client.get("/v1/chatwoot/conversations?status=pending&page=2&limit=15", headers=HEADERS)
    assert result.status_code == 200
    assert adapter.calls[-1] == ("conversations", {"status": "pending", "page": 2, "limit": 15})
    assert client.get("/v1/chatwoot/conversations?limit=51", headers=HEADERS).status_code == 422
    assert client.get("/v1/chatwoot/conversations?status=invalid", headers=HEADERS).status_code == 422
    assert client.get("/v1/chatwoot/conversations/9007199254740992/messages", headers=HEADERS).status_code == 422
    assert client.get("/v1/chatwoot/conversations/5/messages?before=6&limit=10", headers=HEADERS).status_code == 200
    assert adapter.calls[-1] == ("messages", 5, {"before": 6, "limit": 10})


@pytest.mark.parametrize("body", [
    {"content": "Hi"}, {"content": "Hi", "confirmed": False},
    {"content": "Hi", "confirmed": "true"}, {"content": "Hi", "confirmed": 1},
    {"content": "Hi", "confirmed": True, "account_id": 999},
    {"content": "Hi", "confirmed": True, "organization_id": "org-b"},
    {"content": " ", "confirmed": True}, {"content": "x" * 4001, "confirmed": True},
])
def test_replies_require_exact_confirmation_and_forbid_target_injection(monkeypatch, body):
    client, _, adapter, _ = make_client(monkeypatch)
    result = client.post("/v1/chatwoot/conversations/5/messages", headers=HEADERS, json=body)
    assert result.status_code == 422
    assert adapter.calls == []


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_reply_role_and_confirmation_authorize_one_send(monkeypatch, caplog, role):
    client, _, adapter, _ = make_client(monkeypatch, role)
    caplog.set_level("INFO", logger="kiara_api.chatwoot")
    result = client.post("/v1/chatwoot/conversations/5/messages", headers=HEADERS,
                         json={"content": "Private support draft", "confirmed": True})
    assert result.status_code == 200
    assert adapter.calls == [("send", 5, "Private support draft")]
    assert result.json()["automatic_retry"] is False
    assert result.headers["cache-control"] == "no-store"
    assert "Private support draft" not in caplog.text
    assert "synthetic-chatwoot-token" not in caplog.text
    viewer, _, second, _ = make_client(monkeypatch, "viewer")
    assert viewer.post("/v1/chatwoot/conversations/5/messages", headers=HEADERS,
                       json={"content": "Hi", "confirmed": True}).status_code == 403
    assert second.calls == []


def test_operator_cannot_approve_outbound_even_with_confirmation(monkeypatch):
    client, repository, adapter, _ = make_client(monkeypatch, "operator")
    result = client.post("/v1/chatwoot/conversations/5/messages", headers=HEADERS,
                         json={"content": "Hi", "confirmed": True})
    assert result.status_code == 403
    assert repository.reads == []
    assert adapter.calls == []


def test_ambiguous_delivery_is_not_retried_and_errors_are_redacted(monkeypatch):
    client, _, adapter, _ = make_client(monkeypatch)
    adapter.fail = True
    result = client.post("/v1/chatwoot/conversations/5/messages", headers=HEADERS,
                         json={"content": "Hello", "confirmed": True})
    assert result.status_code == 502
    assert result.json()["code"] == "chatwoot_delivery_unknown"
    assert len(adapter.calls) == 1
    assert "Secret or provider payload" not in result.text


@pytest.mark.parametrize("endpoint", ["http://support.example.com", "https://localhost",
    "https://127.0.0.1", "https://10.0.0.1", "https://[::1]", "https://user:pass@example.com",
    "https://support.example.com/api", "https://support.example.com?token=x", "https://example.com:bad",
    "https://support.\nexample.com"])
def test_web_chatwoot_credentials_require_public_https_base(endpoint):
    with pytest.raises(ApiError):
        _validate_credentials("chatwoot", {**CREDENTIALS, "endpoint_url": endpoint})


def test_chatwoot_credentials_require_valid_account_and_token():
    _validate_credentials("chatwoot", CREDENTIALS)
    for change in ({"account_id": "../3"}, {"account_id": "0"},
                   {"api_access_token": "bad\ntoken"}, {"api_access_token": ""}):
        with pytest.raises(ApiError):
            _validate_credentials("chatwoot", {**CREDENTIALS, **change})


@pytest.mark.asyncio
async def test_chatwoot_credentials_remain_encrypted_and_org_scoped():
    observations = []

    class Cursor:
        async def fetchone(self):
            return None

    class Connection:
        async def execute(self, sql, args):
            observations.append((sql, args))
            return Cursor()

    class Postgres:
        @asynccontextmanager
        async def _transaction(self, organization):
            assert organization == "11111111-1111-1111-1111-111111111111"
            yield Connection()

    repo = IntegrationRepository(Postgres(), Fernet.generate_key().decode())
    assert await repo.credentials_for("11111111-1111-1111-1111-111111111111", "chatwoot") is None
    sql, args = observations[0]
    assert args[0] == "chatwoot"
    assert "provider NOT IN ('chatwoot','postiz')" in sql
    encrypted = repo._cipher.encrypt(b'{"api_access_token":"synthetic"}').decode()
    assert "synthetic" not in encrypted
    assert repo.decrypt_for_provider(encrypted) == {"api_access_token": "synthetic"}


def test_migration_extends_provider_constraint():
    sql = (Path(__file__).parents[1] / "migrations/0027_chatwoot_integration.sql").read_text()
    assert "'chatwoot'" in sql
    assert "VALIDATE CONSTRAINT integration_credentials_provider_check" in sql


def test_real_app_factory_registers_chatwoot_with_database_and_cipher_configured():
    from kiara_api.config import ApiSettings
    from kiara_api.main import create_app

    app = create_app(ApiSettings(
        environment="test", database_url="postgresql://synthetic:synthetic@db.invalid/kiara",
        integration_encryption_key=Fernet.generate_key().decode(),
    ))
    # Schema construction does not enter lifespan or open a database connection.
    paths = app.openapi()["paths"]
    assert "get" in paths["/v1/chatwoot/inboxes"]
    assert "get" in paths["/v1/chatwoot/conversations"]
    assert {"get", "post"} <= paths["/v1/chatwoot/conversations/{conversation_id}/messages"].keys()
