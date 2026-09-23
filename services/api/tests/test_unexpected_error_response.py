import sys
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

from kiara_api.hunter import SearchCreate
from kiara_api.main import create_app


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
                "Tipo: RuntimeError. A ocorrência foi registrada para diagnóstico."
            ),
            "request_id": "settings-save-test",
            "details": {"error_type": "RuntimeError"},
        }
    }
    assert "database detail" not in response.text


def test_database_connection_errors_are_explicit_and_retryable():
    app = create_app()

    @app.get("/test/database-unavailable")
    async def database_unavailable():
        raise psycopg.OperationalError("secret connection detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/test/database-unavailable",
            headers={"X-Correlation-ID": "database-unavailable-test"},
        )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "2"
    assert response.json()["error"] == {
        "code": "database_unavailable",
        "message": "O banco de dados está temporariamente indisponível. A operação pode ser repetida.",
        "request_id": "database-unavailable-test",
        "details": {"retryable": True},
    }
    assert "secret connection detail" not in response.text


def test_database_policy_errors_identify_the_rejected_policy_without_leaking_sql():
    app = create_app()

    @app.get("/test/database-policy")
    async def database_policy():
        raise psycopg.errors.InsufficientPrivilege("secret policy detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/test/database-policy",
            headers={"X-Correlation-ID": "database-policy-test"},
        )

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "database_policy_rejected",
        "message": "Uma política de segurança do banco rejeitou a operação. A ocorrência foi registrada.",
        "request_id": "database-policy-test",
        "details": {"retryable": False, "database_code": "42501"},
    }
    assert "secret policy detail" not in response.text


def test_known_database_constraints_return_actionable_messages():
    class Diagnostic:
        constraint_name = "hunter_searches_result_limit_check"

    class ResultLimitViolation(psycopg.errors.CheckViolation):
        @property
        def diag(self):
            return Diagnostic()

    app = create_app()

    @app.get("/test/result-limit-policy")
    async def result_limit_policy():
        raise ResultLimitViolation("secret row detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/test/result-limit-policy",
            headers={"X-Correlation-ID": "result-limit-test"},
        )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "hunter_result_limit_invalid",
        "message": "Informe um limite entre 1 e 100 resultados.",
        "request_id": "result-limit-test",
        "details": {
            "retryable": False,
            "database_code": "23514",
            "constraint": "hunter_searches_result_limit_check",
        },
    }
    assert "secret row detail" not in response.text


def test_request_validation_errors_identify_field_and_action() -> None:
    app = create_app()

    @app.post("/test/validated")
    async def validated(payload: SearchCreate):
        return payload

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/test/validated",
            json={"market": "b2b", "query": "dentistas", "location": "x" * 161,
                  "sources": ["web", "google_maps", "instagram", "facebook"]},
            headers={"X-Correlation-ID": "validation-test"},
        )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "hunter_location_invalid",
        "message": "A cidade ou região deve ter no máximo 160 caracteres.",
        "request_id": "validation-test",
        "details": {
            "field": "location", "reason": "string_too_long",
            "action": "Resuma a localização, por exemplo: Porto Alegre - RS.", "retryable": False,
        },
    }
