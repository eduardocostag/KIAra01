"""The API shares a small pool of database connections per server instance (adapters/postgres.py)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from kiara_api.adapters import postgres
from kiara_api.adapters.postgres import PostgresRepository, connection_mode, pooled_url
from kiara_api.http.errors import ApiError


def test_supabase_session_pooler_is_moved_to_the_transaction_port(monkeypatch):
    monkeypatch.delenv("KIARA_DB_SESSION_POOLER", raising=False)
    session = "postgresql://kiara_app.ref:pw@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
    moved = pooled_url(session)
    assert moved == "postgresql://kiara_app.ref:pw@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    assert connection_mode(moved) == "supabase-transaction-pooler"
    assert pooled_url(moved) == moved                                       # already on the transaction port
    direct = "postgresql://postgres:pw@db.ref.supabase.co:5432/postgres"
    assert pooled_url(direct) == direct and connection_mode(direct) == "direct"
    monkeypatch.setenv("KIARA_DB_SESSION_POOLER", "1")
    assert pooled_url(session) == session                                   # explicit opt-out


class FakeConnection:
    def __init__(self, log):
        self.log, self.closed, self.autocommit, self.row_factory = log, False, False, None

    async def commit(self):
        self.log.append("commit")

    async def rollback(self):
        self.log.append("rollback")

    async def set_autocommit(self, value):
        self.autocommit = value
        self.log.append(f"autocommit={value}")

    async def close(self):
        self.closed = True


class FakePool:
    def __init__(self, log, busy=False):
        self.log, self.busy = log, busy
        self.connection = FakeConnection(log)

    async def getconn(self):
        from psycopg_pool import PoolTimeout
        if self.busy:
            raise PoolTimeout("all busy")
        self.log.append("get")
        return self.connection

    async def putconn(self, connection):
        self.log.append("put")


def test_a_leased_connection_is_committed_or_rolled_back_and_always_returned(monkeypatch):
    log = []
    pool = FakePool(log)

    async def pool_for(url):
        return pool

    monkeypatch.setattr(postgres, "_pool_for", pool_for)
    repository = PostgresRepository("postgresql://localhost/example")

    async def ok():
        async with await repository._connect() as connection:
            assert connection is pool.connection and connection.row_factory is not None

    async def fails():
        async with await repository._connect():
            raise ValueError("boom")

    async def migration():
        async with await repository._connect() as connection:
            await connection.set_autocommit(True)

    asyncio.run(ok())
    assert log == ["get", "commit", "put"]
    log.clear()
    try:
        asyncio.run(fails())
    except ValueError:
        pass
    assert log == ["get", "rollback", "put"]
    log.clear()
    asyncio.run(migration())
    assert log == ["get", "autocommit=True", "autocommit=False", "put"]   # back to the pool's default


def test_when_every_connection_is_busy_the_answer_is_a_friendly_503(monkeypatch):
    async def pool_for(url):
        return FakePool([], busy=True)

    monkeypatch.setattr(postgres, "_pool_for", pool_for)
    repository = PostgresRepository("postgresql://localhost/example")

    async def run():
        async with await repository._connect():
            pass

    try:
        asyncio.run(run())
    except ApiError as error:
        assert error.status_code == 503 and error.code == "database_busy"
    else:
        raise AssertionError("A full pool must answer 503, not hang or crash.")


def test_the_workspace_row_is_written_once_per_instance(monkeypatch):
    executed = []

    class Connection(FakeConnection):
        async def execute(self, sql, params=None):
            executed.append(sql.split()[0])

        def transaction(self):
            class Tx:
                async def __aenter__(self_inner):
                    return None

                async def __aexit__(self_inner, *args):
                    return None
            return Tx()

    class Pool(FakePool):
        def __init__(self):
            super().__init__([])
            self.connection = Connection([])

    pool = Pool()

    async def pool_for(url):
        return pool

    monkeypatch.setattr(postgres, "_pool_for", pool_for)
    monkeypatch.setattr(postgres, "_ENSURED_ORGANIZATIONS", set())
    repository = PostgresRepository("postgresql://localhost/example")

    async def run():
        for _ in range(3):
            async with repository._transaction("00000000-0000-4000-8000-000000000001"):
                pass

    asyncio.run(run())
    assert executed == ["SELECT", "INSERT", "SELECT", "SELECT"]
