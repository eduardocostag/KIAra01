import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from psycopg.types.json import Jsonb

sys.path.insert(0, str(Path(__file__).parents[1]))

from kiara_api.sales import SalesRepository


class FakeConnection:
    def __init__(self):
        self.params = None

    async def execute(self, _query, params):
        self.params = params


class FakePostgres:
    def __init__(self):
        self.connection = FakeConnection()

    @asynccontextmanager
    async def _transaction(self, _organization_id):
        yield self.connection


def test_profile_templates_are_adapted_as_jsonb_before_database_write():
    postgres = FakePostgres()
    repository = SalesRepository(postgres)
    saved = {
        "business_name": "Kiara",
        "sender_name": "Eduardo",
        "offer": "Prospecção",
        "tone": "direto",
        "follow_up_hours": 48,
        "contact_start": "09:00",
        "contact_end": "18:00",
        "templates": {"first_contact": "Olá, {nome}", "custom_orcamento": "Tudo bem?"},
    }

    async def get_profile(_organization_id):
        return saved

    repository.get_profile = get_profile
    result = asyncio.run(repository.save_profile("org-test", saved))

    assert result == saved
    assert isinstance(postgres.connection.params[-1], Jsonb)
    assert postgres.connection.params[-1].obj == saved["templates"]
