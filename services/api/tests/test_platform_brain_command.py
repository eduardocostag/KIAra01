
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from kiara_api.http.errors import ApiError
from kiara_api.platform.access import PlatformAccessRepository
from kiara_api.platform.executors.base import ExecutionResult
from kiara_api.platform.executors.factory import ExecutorFactory
from kiara_api.platform.router import create_platform_router
from kiara_api.platform.service import PLATFORM_ADMIN_EMAILS
from kiara_api.ports.identity import IdentityPrincipal


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
                raise ApiError(401, "invalid_token", "Invalid token")
            return identity

    app = FastAPI()
    app.state.identity_verifier = Verifier()

    @app.middleware("http")
    async def correlation(request, call_next):
        request.state.correlation_id = "brain-test"
        return await call_next(request)

    app.include_router(create_platform_router(PlatformAccessRepository(db)))
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
    admin_identity = principal(email=next(iter(PLATFORM_ADMIN_EMAILS)))
    admin_client = client(identity=admin_identity)

    # Mock the executor to avoid actual external calls
    class MockWan2_1Executor:
        async def execute(self, prompt: str, metadata: dict | None = None):
            return ExecutionResult(True, "mock_video.mp4", "Test video generation")
    monkeypatch.setitem(ExecutorFactory._executors, "wan2_1", MockWan2_1Executor)

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
    admin_identity = principal(email=next(iter(PLATFORM_ADMIN_EMAILS)))
    admin_client = client(identity=admin_identity)

    class MockVoiceStudioExecutor:
        async def execute(self, prompt: str, metadata: dict | None = None):
            return ExecutionResult(True, "mock_audio.mp3", "Test voice generation")
    class MockMoneyPrinterTurboExecutor:
        async def execute(self, prompt: str, metadata: dict | None = None):
            return ExecutionResult(True, "mock_viral_video.mp4", "Test video generation")

    monkeypatch.setitem(ExecutorFactory._executors, "voice_studio", MockVoiceStudioExecutor)
    monkeypatch.setitem(ExecutorFactory._executors, "money_printer_turbo", MockMoneyPrinterTurboExecutor)

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


@pytest.mark.parametrize("prompt", ["Gere um vídeo", "Fale com voz", "Abra o navegador"])
def test_brain_command_reports_missing_integrations_without_fictional_artifacts(prompt):
    result = client().post("/v1/platform/brain/command", headers=AUTH, json={"prompt": prompt})
    assert result.status_code == 200
    outcomes = result.json()["results"]
    assert outcomes
    assert all(item["success"] is False and item["output"] is None for item in outcomes)
