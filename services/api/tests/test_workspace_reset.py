from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from kiara_api.http.context import RequestContext
from kiara_api.workspace import PostgresWorkspaceResetRepository


class Cursor:
    def __init__(self, row=None) -> None:
        self._row = row

    async def fetchone(self):
        return self._row


class Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    async def execute(self, query: str, params: tuple = ()) -> Cursor:
        normalized = " ".join(query.split())
        self.calls.append((normalized, params))
        if normalized.startswith("SELECT count(*) AS count"):
            return Cursor({"count": 2})
        return Cursor()


class Postgres:
    def __init__(self) -> None:
        self.connection = Connection()
        self.organizations: list[str] = []

    @asynccontextmanager
    async def _transaction(self, organization_id: str):
        self.organizations.append(organization_id)
        yield self.connection


def test_reset_is_atomic_tenant_scoped_and_preserves_configuration() -> None:
    postgres = Postgres()
    repository = PostgresWorkspaceResetRepository(postgres)  # type: ignore[arg-type]
    context = RequestContext("user_a", "org_a", "membership_a", "owner", "request-1")

    result = asyncio.run(repository.reset_commercial_data(context))

    assert postgres.organizations == ["org_a"]
    assert result == {
        "leads": 2,
        "pipeline_entries": 2,
        "searches": 2,
        "conversations": 2,
        "activities": 2,
    }
    deletes = [(query, params) for query, params in postgres.connection.calls if query.startswith("DELETE FROM")]
    assert len(deletes) == 12
    assert all("WHERE organization_id=%s" in query and len(params) == 1 for query, params in deletes)
    assert deletes.index(next(item for item in deletes if item[0].startswith("DELETE FROM pipeline_entries"))) < deletes.index(next(item for item in deletes if item[0].startswith("DELETE FROM consumers")))
    assert not any("sales_profiles" in query or "integration_credentials" in query for query, _ in deletes)
    assert any("workspace.commercial_data.reset" in query for query, _ in postgres.connection.calls)
