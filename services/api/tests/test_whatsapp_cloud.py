import hashlib
import hmac
import json

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from kiara_api import whatsapp_cloud
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError

ORG = "6f1c2c1e-1111-4222-8333-944444444444"
SETTINGS = {"META_APP_ID": "1234567890", "META_APP_SECRET": "app-secret", "META_WA_CONFIG_ID": "987654321",
            "META_GRAPH_VERSION": "v23.0", "KIARA_API_PUBLIC_URL": "https://api.kiara.example"}


class FakeIntegrations:
    def __init__(self):
        self.saved = {}
        self._postgres = None

    async def credentials_for(self, organization_id, provider):
        return self.saved.get((organization_id, provider))

    async def save(self, organization_id, provider, credentials, *, is_global=False):
        self.saved[(organization_id, provider)] = dict(credentials)

    async def disconnect(self, organization_id, provider):
        self.saved.pop((organization_id, provider), None)


def fake_graph(calls, fail_on=None):
    def call(method, path, *, version, token=None, params=None, body=None, timeout=20):
        calls.append((method, path, token, params, body))
        if fail_on and fail_on in path:
            raise whatsapp_cloud.GraphError(400, 100, "Número inválido")
        if path == "oauth/access_token":
            return {"access_token": "EAAG-business-token-xyz", "token_type": "bearer"}
        if path.endswith("/messages"):
            return {"messages": [{"id": "wamid.ABC"}]}
        if method == "GET":
            return {"display_phone_number": "+55 51 3333-4444", "verified_name": "Clínica Sorriso", "quality_rating": "GREEN"}
        return {"success": True}
    return call


def build(monkeypatch, *, role="owner", settings=SETTINGS, fail_on=None):
    for key in SETTINGS:
        monkeypatch.delenv(key, raising=False)
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    integrations, calls = FakeIntegrations(), []
    service = whatsapp_cloud.WhatsAppCloudService(integrations, graph_call=fake_graph(calls, fail_on))
    app = FastAPI()
    app.include_router(whatsapp_cloud.create_whatsapp_cloud_router(service))

    @app.exception_handler(ApiError)
    async def error(_request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status_code)

    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", ORG, "m", role, "req", email="dono@clinica.com")
    return TestClient(app), integrations, calls


CONNECT = {"code": "AQBx-code_from.meta", "waba_id": "102030405060", "phone_number_id": "908070605040"}


def test_status_gives_the_browser_only_public_values(monkeypatch):
    api, _, _ = build(monkeypatch)
    body = api.get("/v1/whatsapp-official/status").json()
    assert body == {"connected": False, "platform_ready": True, "app_id": "1234567890", "config_id": "987654321", "graph_version": "v23.0"}
    assert "app-secret" not in json.dumps(body)


def test_platform_not_configured_blocks_connect_and_hides_details_from_clients(monkeypatch):
    api, _, _ = build(monkeypatch, settings={})
    body = api.get("/v1/whatsapp-official/status").json()
    assert body["platform_ready"] is False and "missing_settings" not in body and body["app_id"] == ""
    assert api.post("/v1/whatsapp-official/connect", json=CONNECT).status_code == 503


def test_connect_exchanges_subscribes_registers_and_stores_encrypted(monkeypatch):
    api, integrations, calls = build(monkeypatch)
    response = api.post("/v1/whatsapp-official/connect", json=CONNECT)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["connected"] and body["registered"] and body["verified_name"] == "Clínica Sorriso"
    assert "EAAG" not in response.text and "pin" not in body  # token and PIN never reach the browser
    steps = [(method, path) for method, path, *_ in calls]
    assert steps == [("GET", "oauth/access_token"), ("POST", "102030405060/subscribed_apps"),
                     ("POST", "908070605040/register"), ("GET", "908070605040")]
    subscribe = calls[1][4]
    assert subscribe["override_callback_uri"] == f"https://api.kiara.example/v1/channels/whatsapp-cloud/{ORG}/webhook"
    stored = integrations.saved[(ORG, "whatsapp_cloud")]
    assert stored["access_token"] == "EAAG-business-token-xyz" and stored["verify_token"] == subscribe["verify_token"]
    assert len(stored["pin"]) == 6 and stored["pin"].isdigit() and calls[2][4]["pin"] == stored["pin"]


def test_failed_connection_leaves_nothing_behind(monkeypatch):
    api, integrations, _ = build(monkeypatch, fail_on="subscribed_apps")
    response = api.post("/v1/whatsapp-official/connect", json=CONNECT)
    assert response.status_code == 502 and "Número inválido" in response.text
    assert integrations.saved == {}


def test_only_owner_or_admin_connects(monkeypatch):
    api, _, _ = build(monkeypatch, role="operator")
    assert api.post("/v1/whatsapp-official/connect", json=CONNECT).status_code == 403


def test_webhook_payload_becomes_inbox_messages():
    payload = {"object": "whatsapp_business_account", "entry": [{"id": "102030405060", "changes": [{"field": "messages", "value": {
        "metadata": {"phone_number_id": "908070605040"},
        "contacts": [{"wa_id": "5551999990000", "profile": {"name": "Maria"}}],
        "messages": [
            {"from": "5551999990000", "id": "wamid.1", "timestamp": "1794672190", "type": "text", "text": {"body": "Oi, quanto custa?"}},
            {"from": "5551999990000", "id": "wamid.2", "timestamp": "1794672200", "type": "image", "image": {"caption": ""}},
            {"from": "5551999990000", "id": "wamid.3", "timestamp": "1794672210", "type": "sticker", "sticker": {}},
        ]}}]}]}
    messages = whatsapp_cloud.cloud_messages(payload, "908070605040")
    assert [m["text"] for m in messages] == ["Oi, quanto custa?", "[imagem]", "[figurinha]"]
    assert messages[0]["identity"] == "5551999990000" and messages[0]["name"] == "Maria" and messages[0]["direction"] == "inbound"
    try:
        whatsapp_cloud.cloud_messages(payload, "111111111")
    except ValueError:
        pass
    else:
        raise AssertionError("events for another number must be rejected")


def test_webhook_rejects_unsigned_events(monkeypatch):
    api, integrations, _ = build(monkeypatch)
    integrations.saved[(ORG, "whatsapp_cloud")] = {"phone_number_id": "908070605040", "verify_token": "vt", "access_token": "t", "waba_id": "1"}

    async def fake_credentials(repository, organization_id, provider):
        return integrations.saved[(organization_id, provider)]

    monkeypatch.setattr(whatsapp_cloud, "credentials_for_webhook", fake_credentials)
    raw = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()
    assert api.post(f"/v1/channels/whatsapp-cloud/{ORG}/webhook", content=raw,
                    headers={"x-hub-signature-256": "sha256=forged"}).status_code == 401
    good = "sha256=" + hmac.new(b"app-secret", raw, hashlib.sha256).hexdigest()
    challenge = api.get(f"/v1/channels/whatsapp-cloud/{ORG}/webhook",
                        params={"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "42"})
    assert challenge.status_code == 200 and challenge.text == "42"
    assert api.get(f"/v1/channels/whatsapp-cloud/{ORG}/webhook",
                   params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"}).status_code == 401
    assert good.startswith("sha256=")


def test_send_text_uses_the_clients_number(monkeypatch):
    calls = []
    monkeypatch.setattr(whatsapp_cloud, "graph", fake_graph(calls))
    receipt = whatsapp_cloud.send_text({"phone_number_id": "908070605040", "access_token": "tok"}, "5551999990000", "Olá!")
    assert receipt == "wamid.ABC"
    method, path, token, _params, body = calls[0]
    assert (method, path, token) == ("POST", "908070605040/messages", "tok")
    assert body == {"messaging_product": "whatsapp", "recipient_type": "individual", "to": "5551999990000", "type": "text", "text": {"body": "Olá!"}}
