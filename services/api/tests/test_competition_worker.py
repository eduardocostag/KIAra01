from __future__ import annotations

from typing import Any

import pytest
from kiara_api.browser_worker import BrowserWorkerError
from kiara_api.competition_worker import process_job


class _Repository:
    def __init__(self) -> None:
        self.checkpoints: list[dict[str, Any]] = []
        self.saved_analysis: dict[str, Any] | None = None
        self.saved_prospects: list[dict[str, Any]] = []
        self.finished: dict[str, Any] | None = None

    async def checkpoint_kiara_job(
        self, _organization_id: str, _job_id: str, _worker_id: str, checkpoint
    ):
        self.checkpoints.append(checkpoint)

    async def upsert_analysis(self, organization_id: str, analysis_id: str, snapshot, **kwargs):
        self.saved_analysis = {
            "organization_id": organization_id,
            "analysis_id": analysis_id,
            "snapshot": snapshot,
            **kwargs,
        }

    async def upsert_prospects(self, _organization_id: str, _analysis_id: str, prospects, **_kwargs):
        self.saved_prospects = prospects
        return len(prospects)

    async def finish_kiara_job(self, _organization_id: str, _job_id: str, **kwargs):
        self.finished = kwargs


class _WorkerClient:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def analyse(self, organization_id: str, payload: dict[str, Any]):
        self.calls.append((organization_id, payload))
        if self.error:
            raise self.error
        return self.result


def _job(mode: str = "followers") -> dict[str, Any]:
    return {
        "id": "7f02e6b0-1f6d-49e8-94d4-a4818e49d3c3",
        "organization_id": "org-test",
        "provider_analysis_id": "kiara_test",
        "mode": mode,
        "target": "@example",
        "normalized_target": "https://www.instagram.com/example/",
        "media_id": "media-1",
        "name": "Teste",
        "attempt_count": 1,
        "lease_owner": "worker-1",
    }


@pytest.mark.asyncio
async def test_worker_persists_results_and_marks_job_completed() -> None:
    repository = _Repository()
    client = _WorkerClient(
        {
            "items": [{"id": "instagram:123", "username": "example"}],
            "snapshot": {"source": "instagram"},
        }
    )

    await process_job(repository, client, _job())

    assert client.calls == [
        (
            "org-test",
            {"mode": "followers", "username": "example", "media_id": "media-1", "limit": 25},
        )
    ]
    assert repository.saved_analysis is not None
    assert repository.saved_analysis["analysis_id"] == "kiara_test"
    assert repository.saved_analysis["job_id"] == _job()["id"]
    assert repository.saved_analysis["worker_id"] == "worker-1"
    assert repository.saved_prospects == [{"id": "instagram:123", "username": "example"}]
    assert repository.checkpoints[1]["collection_result"] == {
        "items": [{"id": "instagram:123", "username": "example"}],
        "snapshot": {"source": "instagram"},
    }
    assert repository.finished is not None
    assert repository.finished["state"] == "completed"
    assert repository.finished["checkpoint"]["items_saved"] == 1


@pytest.mark.asyncio
async def test_worker_resumes_from_collected_checkpoint_without_requerying_instagram() -> None:
    repository = _Repository()
    client = _WorkerClient()
    job = _job()
    job["checkpoint"] = {
        "phase": "persisting",
        "items_collected": 1,
        "collection_result": {
            "items": [{"id": "instagram:123", "username": "example"}],
            "snapshot": {"source": "instagram"},
        },
    }

    await process_job(repository, client, job)

    assert client.calls == []
    assert repository.saved_prospects == [{"id": "instagram:123", "username": "example"}]
    assert repository.finished is not None
    assert repository.finished["state"] == "completed"


@pytest.mark.asyncio
async def test_worker_schedules_transient_failure_with_bounded_backoff() -> None:
    repository = _Repository()
    client = _WorkerClient(
        error=BrowserWorkerError(503, "browser_worker_unavailable", "worker offline")
    )
    job = _job()
    job["attempt_count"] = 3

    await process_job(repository, client, job)

    assert repository.finished is not None
    assert repository.finished["state"] == "queued"
    assert repository.finished["retry_after"] == 60


@pytest.mark.asyncio
async def test_worker_pauses_on_rate_limit_and_does_not_retry_verification_challenge() -> None:
    paused_repository = _Repository()
    await process_job(
        paused_repository,
        _WorkerClient(
            error=BrowserWorkerError(
                429,
                "instagram_rate_limited",
                "rate limited",
                retry_after=3_600,
            )
        ),
        _job(),
    )
    assert paused_repository.finished is not None
    assert paused_repository.finished["state"] == "paused"
    assert paused_repository.finished["retry_after"] == 3_600

    challenge_repository = _Repository()
    await process_job(
        challenge_repository,
        _WorkerClient(
            error=BrowserWorkerError(
                409,
                "instagram_verification_required",
                "verification required",
                retry_after=86_400,
            )
        ),
        _job(),
    )
    assert challenge_repository.finished is not None
    assert challenge_repository.finished["state"] == "failed"
