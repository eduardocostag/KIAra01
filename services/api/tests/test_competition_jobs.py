from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from kiara_api.competition_store import CompetitionRepository
from kiara_api.http.errors import ApiError


class _Cursor:
    def __init__(self, row: dict[str, Any] | None = None, rowcount: int = 0) -> None:
        self._row = row
        self.rowcount = rowcount

    async def fetchone(self) -> dict[str, Any] | None:
        return self._row


class _JobConnection:
    def __init__(self) -> None:
        self.jobs: dict[tuple[Any, str], dict[str, Any]] = {}
        self.queues: dict[tuple[Any, Any], dict[str, Any]] = {}

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> _Cursor:
        if query.startswith("INSERT INTO competition_analysis_jobs"):
            (
                organization_id,
                job_id,
                key,
                fingerprint,
                provider_analysis_id,
                mode,
                target,
                normalized_target,
                media_id,
                name,
            ) = params
            self.jobs.setdefault(
                (organization_id, key),
                {
                    "id": job_id,
                    "idempotency_key": key,
                    "request_fingerprint": fingerprint,
                    "provider_analysis_id": provider_analysis_id,
                    "mode": mode,
                    "target": target,
                    "normalized_target": normalized_target,
                    "media_id": media_id,
                    "name": name,
                    "state": "queued",
                    "attempt_count": 0,
                    "checkpoint": {},
                    "error_code": None,
                    "error_message": None,
                    "available_at": datetime.now(UTC),
                    "lease_expires_at": None,
                    "lease_owner": None,
                    "created_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                    "completed_at": None,
                },
            )
            return _Cursor(rowcount=1)
        if query.startswith("SELECT now()"):
            return _Cursor({"current_time": datetime.now(UTC)})
        if query.startswith("SELECT id FROM competition_analysis_jobs") and "FOR UPDATE" in query:
            organization_id, job_id, worker_id = params
            row = next(
                (
                    value
                    for (org, _), value in self.jobs.items()
                    if org == organization_id and str(value["id"]) == str(job_id)
                ),
                None,
            )
            if (
                row is None
                or row["state"] != "running"
                or row["lease_owner"] != worker_id
                or row["lease_expires_at"] <= datetime.now(UTC)
            ):
                return _Cursor()
            return _Cursor({"id": row["id"]})
        if query.startswith("INSERT INTO competition_analysis_work_queue"):
            organization_id, job_id, available_at = params
            self.queues.setdefault(
                (organization_id, job_id),
                {
                    "available_at": available_at,
                    "lease_owner": None,
                    "lease_expires_at": None,
                },
            )
            return _Cursor(rowcount=1)
        if "FROM competition_analysis_jobs" in query:
            if "idempotency_key=%s" in query:
                return _Cursor(self.jobs.get((params[0], params[1])))
            if "id=%s" in query:
                return _Cursor(next(
                    (row for (org, _), row in self.jobs.items()
                     if org == params[0] and row["id"] == params[1]),
                    None,
                ))
        if query.startswith("UPDATE competition_analysis_jobs SET state='running'"):
            organization_id, job_id = params
            row = next(
                (
                    value
                    for (org, _), value in self.jobs.items()
                    if org == organization_id and value["id"] == job_id
                ),
                None,
            )
            if row is None:
                return _Cursor(rowcount=0)
            row.update(
                state="running",
                attempt_count=row["attempt_count"] + 1,
                error_code=None,
                error_message=None,
                lease_expires_at=datetime.now(UTC) + timedelta(minutes=2),
                updated_at=datetime.now(UTC),
            )
            return _Cursor(row, rowcount=1)
        if "UPDATE competition_analysis_jobs" in query and "attempt_count=attempt_count+1" in query:
            worker_id, organization_id, job_id = params
            job_id = str(job_id)
            row = next(
                (
                    value
                    for (org, _), value in self.jobs.items()
                    if org == organization_id and str(value["id"]) == job_id
                ),
                None,
            )
            if row is None or row["state"] not in {"queued", "paused", "running"}:
                return _Cursor(rowcount=0)
            row.update(
                state="running",
                attempt_count=row["attempt_count"] + 1,
                error_code=None,
                error_message=None,
                lease_expires_at=datetime.now(UTC) + timedelta(minutes=3),
                lease_owner=worker_id,
                updated_at=datetime.now(UTC),
            )
            return _Cursor(
                {
                    key: row[key]
                    for key in (
                        "id",
                        "provider_analysis_id",
                        "mode",
                        "target",
                        "normalized_target",
                        "media_id",
                        "name",
                        "state",
                        "attempt_count",
                        "checkpoint",
                        "lease_owner",
                    )
                },
                rowcount=1,
            )
        if "SET checkpoint=%s::jsonb" in query:
            checkpoint, organization_id, job_id, worker_id = params
            row = next(
                (
                    value
                    for (org, _), value in self.jobs.items()
                    if org == organization_id and str(value["id"]) == str(job_id)
                ),
                None,
            )
            if row is None or row["state"] != "running" or row["lease_owner"] != worker_id:
                return _Cursor(rowcount=0)
            row.update(checkpoint=json.loads(checkpoint), lease_expires_at=datetime.now(UTC) + timedelta(minutes=3))
            return _Cursor(rowcount=1)
        if "SET state=%s,checkpoint=%s::jsonb" in query:
            (
                state,
                checkpoint,
                error_code,
                error_message,
                _,
                retry_after,
                _,
                organization_id,
                job_id,
                worker_id,
            ) = params
            job_id = str(job_id)
            row = next(
                (
                    value
                    for (org, _), value in self.jobs.items()
                    if org == organization_id and str(value["id"]) == job_id
                ),
                None,
            )
            if row is None or row["state"] != "running" or row["lease_owner"] != worker_id:
                return _Cursor(rowcount=0)
            now = datetime.now(UTC)
            row.update(
                state=state,
                checkpoint=json.loads(checkpoint),
                error_code=error_code,
                error_message=error_message,
                available_at=now + timedelta(seconds=retry_after) if state == "paused" else now,
                lease_expires_at=None,
                lease_owner=None,
                completed_at=now if state == "completed" else None,
                updated_at=now,
            )
            if state in {"queued", "paused"}:
                self.queues[(organization_id, job_id)] = {
                    "available_at": now + timedelta(seconds=retry_after),
                    "lease_owner": None,
                    "lease_expires_at": None,
                }
            else:
                self.queues.pop((organization_id, job_id), None)
            return _Cursor(rowcount=1)
        if query.startswith("DELETE FROM competition_analysis_work_queue"):
            organization_id, job_id = params
            self.queues.pop((organization_id, str(job_id)), None)
            return _Cursor(rowcount=1)
        raise AssertionError(f"Unexpected SQL: {query}")


class _AsyncContextManager:
    def __init__(self, value: Any) -> None:
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return None


class _GlobalConnection:
    def __init__(self, postgres: _JobPostgres) -> None:
        self.postgres = postgres

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def transaction(self):
        return _AsyncContextManager(self)

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> _Cursor:
        if "WITH candidate AS" in query:
            worker_id = params[0]
            now = datetime.now(UTC)
            candidate = next(
                (
                    (key, queue)
                    for key, queue in self.postgres.connection.queues.items()
                    if queue["available_at"] <= now
                    and (
                        queue["lease_owner"] is None
                        or queue["lease_expires_at"] < now
                    )
                ),
                None,
            )
            if candidate is None:
                return _Cursor()
            (organization_id, job_id), queue = candidate
            queue.update(
                lease_owner=worker_id,
                lease_expires_at=now + timedelta(minutes=3),
            )
            return _Cursor({"organization_id": organization_id, "job_id": job_id})
        if "UPDATE competition_analysis_work_queue SET lease_owner=NULL" in query:
            organization_id, job_id, worker_id = params
            queue = self.postgres.connection.queues.get((organization_id, job_id))
            if queue and queue["lease_owner"] == worker_id:
                queue.update(lease_owner=None, lease_expires_at=None)
            return _Cursor(rowcount=1 if queue else 0)
        raise AssertionError(f"Unexpected global SQL: {query}")


class _JobPostgres:
    def __init__(self) -> None:
        self.connection = _JobConnection()

    @asynccontextmanager
    async def _transaction(self, _organization_id: str):
        yield self.connection

    async def _connect(self, **_kwargs):
        return _GlobalConnection(self)


@pytest.mark.asyncio
async def test_competition_job_replay_enqueues_only_once() -> None:
    postgres = _JobPostgres()
    repository = CompetitionRepository(postgres)  # type: ignore[arg-type]
    parameters = {
        "mode": "followers",
        "target": "@example",
        "normalized_target": "https://www.instagram.com/example/",
        "media_id": None,
        "name": "Example",
    }

    first = await repository.begin_kiara_job("org-a", "request-key-000001", "a" * 64, **parameters)
    replay = await repository.begin_kiara_job("org-a", "request-key-000001", "a" * 64, **parameters)

    assert first["state"] == "queued"
    assert first["attempt_count"] == 0
    assert replay["id"] == first["id"]
    assert replay["attempt_count"] == 0
    assert len(postgres.connection.queues) == 1


@pytest.mark.asyncio
async def test_job_status_does_not_expose_private_collection_checkpoint() -> None:
    postgres = _JobPostgres()
    repository = CompetitionRepository(postgres)  # type: ignore[arg-type]
    job = await repository.begin_kiara_job(
        "org-a",
        "request-key-000001",
        "a" * 64,
        mode="followers",
        target="@example",
        normalized_target="https://www.instagram.com/example/",
        media_id=None,
        name="Example",
    )
    stored = next(iter(postgres.connection.jobs.values()))
    stored["checkpoint"] = {
        "phase": "persisting",
        "items_collected": 1,
        "collection_result": {
            "items": [{"id": "instagram:123", "email": "private@example.com"}],
            "snapshot": {"source": "instagram"},
        },
    }

    status = await repository.get_kiara_job("org-a", job["id"])

    assert status is not None
    assert status["checkpoint"] == {"phase": "persisting", "items_collected": 1}


@pytest.mark.asyncio
async def test_competition_job_rejects_idempotency_key_reuse_for_other_request() -> None:
    repository = CompetitionRepository(_JobPostgres())  # type: ignore[arg-type]
    parameters = {
        "mode": "followers",
        "target": "@example",
        "normalized_target": "https://www.instagram.com/example/",
        "media_id": None,
        "name": "Example",
    }
    await repository.begin_kiara_job("org-a", "request-key-000001", "a" * 64, **parameters)

    with pytest.raises(ApiError) as raised:
        await repository.begin_kiara_job(
            "org-a",
            "request-key-000001",
            "b" * 64,
            **parameters,
        )

    assert raised.value.status_code == 409


@pytest.mark.asyncio
async def test_paused_competition_job_is_scheduled_after_its_cooldown() -> None:
    postgres = _JobPostgres()
    repository = CompetitionRepository(postgres)  # type: ignore[arg-type]
    parameters = {
        "mode": "followers",
        "target": "@example",
        "normalized_target": "https://www.instagram.com/example/",
        "media_id": None,
        "name": "Example",
    }
    first = await repository.begin_kiara_job(
        "org-a", "request-key-000001", "a" * 64, **parameters
    )
    stored = next(iter(postgres.connection.jobs.values()))
    stored["state"] = "running"
    stored["lease_owner"] = "test-worker"
    await repository.finish_kiara_job(
        "org-a",
        first["id"],
        worker_id="test-worker",
        state="paused",
        checkpoint={"phase": "paused"},
        error_code="instagram_rate_limited",
        retry_after=300,
    )

    paused = await repository.begin_kiara_job(
        "org-a", "request-key-000001", "a" * 64, **parameters
    )
    assert paused["state"] == "paused"

    stored["available_at"] = datetime.now(UTC) - timedelta(seconds=1)
    queue = max(
        postgres.connection.queues.values(),
        key=lambda item: item["available_at"],
    )
    assert queue["available_at"] > datetime.now(UTC)
    queue["available_at"] = datetime.now(UTC) - timedelta(seconds=1)
    assert queue["available_at"] < datetime.now(UTC)
    assert stored["state"] == "paused"
    assert stored["attempt_count"] == 0


@pytest.mark.asyncio
async def test_worker_claims_due_job_once_and_increments_attempt_count() -> None:
    postgres = _JobPostgres()
    repository = CompetitionRepository(postgres)  # type: ignore[arg-type]
    await repository.begin_kiara_job(
        "org-a",
        "request-key-000001",
        "a" * 64,
        mode="followers",
        target="@example",
        normalized_target="https://www.instagram.com/example/",
        media_id=None,
        name="Example",
    )

    job = await repository.claim_next_kiara_job("worker-1")

    assert job is not None
    assert job["state"] == "running"
    assert job["attempt_count"] == 1
    assert job["lease_owner"] == "worker-1"
    assert job["normalized_target"] == "https://www.instagram.com/example/"
    assert await repository.claim_next_kiara_job("worker-2") is None


@pytest.mark.asyncio
async def test_expired_worker_cannot_finish_job_after_another_worker_reclaims_it() -> None:
    postgres = _JobPostgres()
    repository = CompetitionRepository(postgres)  # type: ignore[arg-type]
    await repository.begin_kiara_job(
        "org-a",
        "request-key-000001",
        "a" * 64,
        mode="followers",
        target="@example",
        normalized_target="https://www.instagram.com/example/",
        media_id=None,
        name="Example",
    )
    first_claim = await repository.claim_next_kiara_job("worker-1")
    assert first_claim is not None

    now = datetime.now(UTC) - timedelta(seconds=1)
    stored = next(iter(postgres.connection.jobs.values()))
    stored["lease_expires_at"] = now
    queue = next(iter(postgres.connection.queues.values()))
    queue["lease_expires_at"] = now
    second_claim = await repository.claim_next_kiara_job("worker-2")
    assert second_claim is not None
    assert second_claim["lease_owner"] == "worker-2"
    assert isinstance(second_claim["id"], str)

    with pytest.raises(ApiError) as stale_persist:
        await repository._assert_kiara_job_lease(
            postgres.connection,
            "org-a",
            first_claim["id"],
            "worker-1",
        )
    assert stale_persist.value.status_code == 409
    await repository._assert_kiara_job_lease(
        postgres.connection,
        "org-a",
        second_claim["id"],
        "worker-2",
    )

    with pytest.raises(ApiError) as stale_checkpoint:
        await repository.checkpoint_kiara_job(
            "org-a",
            first_claim["id"],
            "worker-1",
            {"phase": "stale"},
        )
    assert stale_checkpoint.value.status_code == 409

    with pytest.raises(ApiError) as raised:
        await repository.finish_kiara_job(
            "org-a",
            first_claim["id"],
            worker_id="worker-1",
            state="completed",
            checkpoint={"phase": "completed"},
        )
    assert raised.value.status_code == 409

    await repository.finish_kiara_job(
        "org-a",
        second_claim["id"],
        worker_id="worker-2",
        state="completed",
        checkpoint={"phase": "completed"},
    )
