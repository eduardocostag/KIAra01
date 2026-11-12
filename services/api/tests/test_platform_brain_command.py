import json

import pytest
from kiara_api.adapters.postgres import _uuid
from kiara_api.http.context import RequestContext
from kiara_api.main import create_app
from kiara_api.platform.access import PlatformAccessRepository
from kiara_api.platform.service import PLATFORM_ADMIN_EMAILS, PlatformService
from kiara_api.ports.identity import IdentityPrincipal
from fastapi.testclient import TestClient


class Connection:
    def __init__(self, organizations, memberships):
        self.organizations, self.memberships = organizations, memberships
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def transaction(self):
        return self

    async def execute(self, query, params=()):
        self.calls.append((query, params))
        if "FROM organizations" in query:
            return Cursor(self.organizations.get(params[0]))
        if "FROM memberships" in query:
            return Cursor(self.memberships.get(tuple(params)))
        assert query == "SET TRANSACTION READ ONLY" or query.startswith("SELECT set_config(")
        return Cursor(None)


class Database:
    def __init__(self, organizations, memberships):
        self.connection = Connection(organizations, memberships)

    async def _connect(self):
        return self.connection


def principal(user="alice", organization=None, role="owner", email=None):
    identity_email = (
        "admin@kiara.local" if user == "alice" else f"{user}@example.test"
    ) if email is None else email
    return IdentityPrincipal(
        user, organization or user, f"{organization or user}:{user}", role, identity_email
    )


def client(identity=None, db=None):
    identity = identity or principal()

    class Verifier:
        async def verify(self, token):
            if token != "valid-token":
                raise Exception("Invalid token")
            return identity

    app = create_app(identity_verifier=Verifier())
    return TestClient(app)


AUTH = {"Authorization": "Bearer valid-token"}

@pytest.fixture(autouse=True)
def clean_policy(monkeypatch):
    monkeypatch.delenv("KIARA_PLATFORM_POLICY_JSON", raising=False)

def test_brain_command_requires_admin_access():
    # Test with a non-admin user
    non_admin_identity = principal(email="user@example.test")
    non_admin_client = client(identity=non_admin_identity)
    response = non_admin_client.post("/v1/platform/brain/command", headers=AUTH, json={"prompt": "gerar vídeo"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "platform_admin_only"

def test_brain_command_processes_video_intent(monkeypatch):
    admin_identity = principal(email=list(PLATFORM_ADMIN_EMAILS)[0])
    admin_client = client(identity=admin_identity)

    # Mock the executor to avoid actual external calls
    class MockWan2_1Executor:
        async def execute(self, prompt: str, metadata: dict = None):
            return {"success": True, "output_path": "mock_video.mp4", "message": "Simulated video generation"}
    monkeypatch.setattr("kiara_api.platform.executors.factory.Wan2_1Executor", MockWan2_1Executor)

    response = admin_client.post("/v1/platform/brain/command", headers=AUTH, json={"prompt": "Gere um vídeo de um gato"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["prompt"] == "Gere um vídeo de um gato"
    assert payload["phase"] == "structure_only"
    assert payload["agent"] == "KIARA Jarvis"
    assert len(payload["execution_plan"]) == 1
    assert payload["execution_plan"][0]["action_type"] == "video_generation"
    assert payload["execution_plan"][0]["target_executor"] == "wan2_1"
    assert len(payload["results"]) == 1
    assert payload["results"][0]["success"] is True
    assert payload["results"][0]["output"] == "mock_video.mp4"

def test_brain_command_processes_multimodal_intent(monkeypatch):
    admin_identity = principal(email=list(PLATFORM_ADMIN_EMAILS)[0])
    admin_client = client(identity=admin_identity)

    class MockVoiceStudioExecutor:
        async def execute(self, prompt: str, metadata: dict = None):
            return {"success": True, "output_path": "mock_audio.mp3", "message": "Simulated voice generation"}
    class MockMoneyPrinterTurboExecutor:
        async def execute(self, prompt: str, metadata: dict = None):
            return {"success": True, "output_path": "mock_viral_video.mp4", "message": "Simulated viral video generation"}

    monkeypatch.setattr("kiara_api.platform.executors.factory.VoiceStudioExecutor", MockVoiceStudioExecutor)
    monkeypatch.setattr("kiara_api.platform.executors.factory.MoneyPrinterTurboExecutor", MockMoneyPrinterTurboExecutor)

    response = admin_client.post("/v1/platform/brain/command", headers=AUTH, json={"prompt": "Crie um vídeo viral com voz sobre IA"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["execution_plan"]) == 2
    assert payload["execution_plan"][0]["action_type"] == "text_to_speech"
    assert payload["execution_plan"][0]["target_executor"] == "voice_studio"
    assert payload["execution_plan"][1]["action_type"] == "viral_video_generation"
    assert payload["execution_plan"][1]["target_executor"] == "money_printer_turbo"
    assert len(payload["results"]) == 2
    assert payload["results"][0]["success"] is True
    assert payload["results"][1]["success"] is True
