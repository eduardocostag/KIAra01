from fastapi import FastAPI
from fastapi.testclient import TestClient

from kiara_api.admin_users import create_admin_users_router
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError
from fastapi.responses import JSONResponse


class FakeResult:
    rowcount = 2


class FakeConnection:
    def __init__(self, log):
        self.log = log

    async def execute(self, sql, params):
        self.log.append((sql.split()[2], params))
        return FakeResult()

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakePostgres:
    def __init__(self):
        self.log = []

    async def _connect(self):
        return FakeConnection(self.log)


def client(email, postgres):
    app = FastAPI()
    app.include_router(create_admin_users_router(postgres))
    app.add_exception_handler(ApiError, lambda request, exc: JSONResponse({"code": exc.code}, status_code=exc.status_code))
    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", "org", "m", "owner", "req", email=email)
    return TestClient(app)


def test_only_system_admins_end_sessions():
    postgres = FakePostgres()
    target = "e1d9ab1f-0000-4000-8000-000000000000"
    assert client("cliente@empresa.com", postgres).post(f"/v1/admin/users/{target}/sign-out").status_code == 403
    assert postgres.log == []
    response = client("eduardocgonsalves@hotmail.com", postgres).post(f"/v1/admin/users/{target}/sign-out")
    assert response.status_code == 200 and response.json() == {"ended_sessions": 2}
    assert [table for table, _ in postgres.log] == ["auth.refresh_tokens", "auth.sessions"]
    assert client("admin@kiara.local", postgres).post("/v1/admin/users/not-a-uuid/sign-out").status_code == 422
