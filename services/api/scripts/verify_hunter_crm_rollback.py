"""Exercise actual SQL in a fresh synthetic tenant and roll back EVERY write.

No existing tenant is queried. Reads only POSTGRES_URL from the API's existing
local environment file; never prints credentials or customer data.
"""
import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.rows import dict_row
from kiara_api.adapters.postgres import PostgresRepository, _psycopg_url, _uuid
from kiara_api.http.context import RequestContext
from kiara_api.hunter import HunterRepository, SearchCreate
from kiara_api.hunter_research import filter_results


class TransactionRepository(PostgresRepository):
    def __init__(self, connection):
        self.connection = connection

    @asynccontextmanager
    async def _transaction(self, organization_id):
        org = _uuid("organization", organization_id)
        async with self.connection.transaction():
            await self.connection.execute("SELECT set_config('app.organization_id',%s,true)", (str(org),))
            await self.connection.execute("INSERT INTO organizations (id,slug,name) VALUES (%s,%s,'Synthetic rollback verification') ON CONFLICT DO NOTHING", (org, f"verify-{org}"))
            yield self.connection


async def main():
    values = {}
    for line in (Path(__file__).resolve().parents[1] / ".env.local").read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key == "POSTGRES_URL":
            values[key] = json.loads(value) if value.startswith('"') else value
    org, second_org = uuid4(), uuid4()
    context = RequestContext(str(uuid4()), str(org), str(uuid4()), "admin", str(uuid4()))
    async with await psycopg.AsyncConnection.connect(_psycopg_url(values["POSTGRES_URL"]), row_factory=dict_row, connect_timeout=10) as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL statement_timeout = '15s'")
            db = TransactionRepository(conn)
            repository = HunterRepository(db)
            payload = SearchCreate(market="b2b", query="profissionais sem site", location="Cidade de teste", sources=["google_maps"], contact_filter="whatsapp")
            created = await repository.create(context, payload)
            claimed = await repository.claim_confirmation(context, created["id"])
            fixtures = [
                {"source": "google_maps", "title": "Synthetic contact", "url": "https://www.google.com/maps/place/Synthetic/data=!1sverification-only", "public_data": {"detail_inspected": True, "website_status": "not_listed", "phone": "+5511987654321", "whatsapp_url": "https://wa.me/5511987654321"}},
                {"source": "web", "title": "Excluded website", "url": "https://example.com", "public_data": {}},
            ]
            accepted, validation = filter_results(fixtures, claimed)
            assert len(accepted) == 1 and validation["excluded"] == 1
            finished = await repository.finish(context, created["id"], accepted, validation=validation)
            assert finished["sync_summary"] == {"created": 1, "existing": 0, "skipped": 0}
            entries = await db.list_entries(str(org))
            assert len(entries) == 1 and entries[0]["consumer"]["instagram_username"] is None
            assert entries[0]["consumer"]["whatsapp_url"] == "https://wa.me/5511987654321"
            assert await db.list_threads(str(org)) == []
            entry = entries[0]
            outcome, updated = await db.update_entry(str(org), entry["id"], str(uuid4()), entry["version"], {"stage": "opportunity"})
            assert outcome == "updated" and updated["stage"] == "opportunity"
            repeated = await repository.create(context, payload)
            await repository.claim_confirmation(context, repeated["id"])
            repeat = await repository.finish(context, repeated["id"], accepted, validation=validation)
            assert repeat["sync_summary"]["existing"] == 1
            entries = await db.list_entries(str(org))
            assert len(entries) == 1 and entries[0]["stage"] == "opportunity"
            assert len(await repository.list(context)) == 2
            assert await db.list_entries(str(second_org)) == []
            print("PASS SQL: strict filters -> saved Hunter -> CRM -> Pipeline, no fake Inbox")
            print("PASS SQL: repeated search deduplicated, manual stage preserved, tenant isolated")
            raise psycopg.Rollback()
        remaining = await (await conn.execute("SELECT count(*) n FROM organizations WHERE id=ANY(%s)", ([org, second_org],))).fetchone()
        assert remaining["n"] == 0
        print("PASS rollback: no synthetic records persisted")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        print(json.dumps({"error_type": type(error).__name__, "sqlstate": getattr(error, "sqlstate", None)}))
        sys.exit(1)
