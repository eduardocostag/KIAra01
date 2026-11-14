from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from kiara_api import db_admin
from kiara_api.http.errors import ApiError


def build(monkeypatch, token="worker-secret"):
    monkeypatch.setenv("KIARA_WORKER_TOKEN", token)
    app = FastAPI()
    app.include_router(db_admin.create_db_admin_router(None))

    @app.exception_handler(ApiError)
    async def error(_request, exc):
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status_code)

    return TestClient(app)


def test_requires_the_worker_token_and_a_valid_migration_name(monkeypatch):
    api = build(monkeypatch)
    assert api.get("/v1/internal/db/status").status_code == 401
    assert api.post("/v1/internal/db/migrate/0031_whatsapp_cloud_integration.sql", headers={"Authorization": "Bearer nope"}).status_code == 401
    auth = {"Authorization": "Bearer worker-secret"}
    assert api.post("/v1/internal/db/migrate/..%2Fsecrets.sql", headers=auth).status_code in {404, 422}
    assert api.post("/v1/internal/db/migrate/0031;drop.sql", headers=auth).status_code == 422
    assert api.post("/v1/internal/db/migrate/9999_missing.sql", headers=auth).status_code == 404


def test_migrations_are_shipped_with_the_release():
    names = sorted(path.name for path in db_admin._migration_dir().glob("*.sql"))
    assert "0031_whatsapp_cloud_integration.sql" in names and all(db_admin._NAME.fullmatch(name) for name in names)
