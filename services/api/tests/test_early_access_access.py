import io
import json

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from kiara_api.chat import create_chat_router
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError
from kiara_api.whatsapp_web import WhatsAppWebRepository, create_whatsapp_web_router

from app.chat.auth import AuthorizationError, SupabaseAuthorizationVerifier


@pytest.mark.parametrize("role", ["owner", "admin", "operator"])
@pytest.mark.parametrize("email", [None, "member@example.com"])
def test_direct_api_cannot_bypass_admin_only_early_access(role, email):
    app = FastAPI()
    app.include_router(create_chat_router())
    app.include_router(create_whatsapp_web_router(WhatsAppWebRepository()))
    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", "org", "m", role, "req", email=email)

    @app.exception_handler(ApiError)
    async def denied(_request, error):
        return JSONResponse({"code": error.code}, status_code=error.status_code)

    client = TestClient(app)
    for path in ["/v1/chat/status", "/v1/whatsapp-web/config"]:
        response = client.get(path)
        assert response.status_code == 403
        assert response.json()["code"] == "system_admin_required"


def test_local_executor_rejects_other_owner_even_with_admin_user_metadata():
    class Opener:
        def __init__(self):
            self.items = iter([
                {"id": "u", "email": "member@example.com", "user_metadata": {"email": "admin@kiara.local"}},
                {"user_id": "u", "role": "owner", "organization": {"id": "org"}},
            ])

        def open(self, *_args, **_kwargs):
            return io.BytesIO(json.dumps(next(self.items)).encode())

    verifier = SupabaseAuthorizationVerifier("https://project.supabase.co", "public", "https://api.example.com", opener=Opener())
    with pytest.raises(AuthorizationError):
        verifier.verify("test-access-token")
