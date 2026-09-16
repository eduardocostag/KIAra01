from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

from kiara_api.main import CorrelationMiddleware, create_app


def test_unexpected_errors_return_json_with_a_traceable_request_id():
    app = create_app()

    @app.get("/test/unexpected-error")
    async def unexpected_error():
        raise RuntimeError("database detail that must stay in server logs")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/test/unexpected-error",
            headers={"X-Correlation-ID": "settings-save-test"},
        )

    assert response.status_code == 500
    assert response.headers["X-Correlation-ID"] == "settings-save-test"
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": (
                "A API encontrou um erro interno ao concluir a operação. "
                "Use o ID da ocorrência para consultar os logs."
            ),
            "request_id": "settings-save-test",
            "details": {},
        }
    }
    assert "database detail" not in response.text
