import asyncio
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).parents[1]))

from kiara_api.adapters.postgres import PostgresRepository


def test_database_connect_retries_transient_operational_errors(monkeypatch):
    attempts = 0
    sentinel = object()

    async def connect(**_options):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise psycopg.OperationalError("temporary pool failure")
        return sentinel

    async def no_wait(_delay):
        return None

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", connect)
    monkeypatch.setattr("kiara_api.adapters.postgres.asyncio.sleep", no_wait)

    repository = PostgresRepository("postgresql://localhost/example")
    assert asyncio.run(repository._connect()) is sentinel
    assert attempts == 3


def test_database_connect_stops_after_bounded_attempts(monkeypatch):
    attempts = 0

    async def connect(**_options):
        nonlocal attempts
        attempts += 1
        raise psycopg.OperationalError("persistent pool failure")

    async def no_wait(_delay):
        return None

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", connect)
    monkeypatch.setattr("kiara_api.adapters.postgres.asyncio.sleep", no_wait)

    repository = PostgresRepository("postgresql://localhost/example")
    try:
        asyncio.run(repository._connect())
    except psycopg.OperationalError:
        pass
    else:
        raise AssertionError("Persistent database errors must be reported after bounded retries.")
    assert attempts == 3
