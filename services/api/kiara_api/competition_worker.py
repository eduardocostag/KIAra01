from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import uuid
from typing import Any
from urllib.parse import urlsplit

from .adapters.postgres import PostgresRepository
from .browser_worker import BrowserWorkerClient, BrowserWorkerError
from .competition_store import CompetitionRepository
from .config import ApiSettings

logger = logging.getLogger("kiara_api.competition_worker")
_MAX_TRANSIENT_ATTEMPTS = 5
_TRANSIENT_ERRORS = {
    "browser_worker_busy",
    "browser_worker_unavailable",
}
_SAFETY_PAUSE_ERRORS = {
    "instagram_rate_limited",
    "instagram_safety_cooldown",
}


async def process_job(
    repository: CompetitionRepository,
    worker_client: BrowserWorkerClient,
    job: dict[str, Any],
) -> None:
    organization_id = str(job["organization_id"])
    job_id = str(job["id"])
    attempt = int(job["attempt_count"])
    worker_id = str(job["lease_owner"])
    target = str(job["normalized_target"])
    checkpoint = job.get("checkpoint")
    checkpoint = dict(checkpoint) if isinstance(checkpoint, dict) else {}
    if job["mode"] == "followers":
        target = (urlsplit(target).path.strip("/").split("/") or [""])[0]

    try:
        collection_result = checkpoint.get("collection_result")
        if isinstance(collection_result, dict):
            items = collection_result.get("items")
            snapshot = collection_result.get("snapshot")
        else:
            checkpoint.update(phase="collecting", items_collected=0)
            await repository.checkpoint_kiara_job(
                organization_id, job_id, worker_id, checkpoint
            )
            result = await asyncio.to_thread(
                worker_client.analyse,
                organization_id,
                {
                    "mode": job["mode"],
                    "username": target,
                    "media_id": job["media_id"],
                    "limit": 25,
                },
            )
            items = result.get("items")
            snapshot = result.get("snapshot", {})
            if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                raise BrowserWorkerError(
                    502,
                    "browser_worker_invalid_response",
                    "O navegador retornou prospectos em formato inválido.",
                )
            if not isinstance(snapshot, dict):
                raise BrowserWorkerError(
                    502,
                    "browser_worker_invalid_response",
                    "O navegador retornou um resumo em formato inválido.",
                )
            checkpoint.update(
                phase="persisting",
                items_collected=len(items),
                collection_result={"items": items, "snapshot": snapshot},
            )
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise BrowserWorkerError(
                502,
                "browser_worker_invalid_response",
                "O checkpoint do navegador contém prospectos inválidos.",
            )
        if not isinstance(snapshot, dict):
            raise BrowserWorkerError(
                502,
                "browser_worker_invalid_response",
                "O checkpoint do navegador contém um resumo inválido.",
            )
        await repository.checkpoint_kiara_job(
            organization_id, job_id, worker_id, checkpoint
        )
        await repository.upsert_analysis(
            organization_id,
            str(job["provider_analysis_id"]),
            {**snapshot, "collected": len(items)},
            mode=str(job["mode"]),
            target=str(job["target"]),
            name=str(job["name"]),
            status="completed",
            prospect_count=len(items),
            provider="kiara_instagram",
            job_id=job_id,
            worker_id=worker_id,
        )
        saved = await repository.upsert_prospects(
            organization_id,
            str(job["provider_analysis_id"]),
            items,
            job_id=job_id,
            worker_id=worker_id,
        )
        await repository.finish_kiara_job(
            organization_id,
            job_id,
            worker_id=worker_id,
            state="completed",
            checkpoint={
                "phase": "completed",
                "items_collected": len(items),
                "items_saved": saved,
            },
        )
        logger.info(
            "competition.job_completed organization_id=%s job_id=%s attempt=%s saved=%s",
            organization_id,
            job_id,
            attempt,
            saved,
        )
    except BrowserWorkerError as error:
        retry_after = error.retry_after or 0
        if error.code in _SAFETY_PAUSE_ERRORS and retry_after <= 0:
            retry_after = 3_600
        if error.code == "instagram_verification_required":
            state = "failed"
        elif retry_after > 0:
            state = "paused"
        elif error.code in _TRANSIENT_ERRORS or error.status_code >= 500:
            state = "queued" if attempt < _MAX_TRANSIENT_ATTEMPTS else "failed"
            if state == "queued":
                retry_after = min(300, 15 * (2 ** max(0, attempt - 1)))
        else:
            state = "failed"
        await repository.finish_kiara_job(
            organization_id,
            job_id,
            worker_id=worker_id,
            state=state,
            checkpoint={**checkpoint, "phase": state},
            error_code=error.code,
            error_message=error.message,
            retry_after=retry_after,
        )
        logger.warning(
            "competition.job_deferred organization_id=%s job_id=%s state=%s code=%s attempt=%s retry_after=%s",
            organization_id,
            job_id,
            state,
            error.code,
            attempt,
            retry_after,
        )
    except Exception as error:
        await repository.finish_kiara_job(
            organization_id,
            job_id,
            worker_id=worker_id,
            state="failed",
            checkpoint={**checkpoint, "phase": "failed"},
            error_code=type(error).__name__,
            error_message=str(error),
        )
        logger.exception(
            "competition.job_failed organization_id=%s job_id=%s attempt=%s",
            organization_id,
            job_id,
            attempt,
        )


async def run_worker(*, once: bool = False, poll_seconds: float = 2.0) -> None:
    settings = ApiSettings.from_env()
    if not settings.database_url:
        raise RuntimeError("POSTGRES_URL or DATABASE_URL is required for the competition worker.")
    repository = CompetitionRepository(PostgresRepository(settings.database_url))
    client = BrowserWorkerClient()
    if not client.configured:
        raise RuntimeError(
            "KIARA_BROWSER_WORKER_URL and KIARA_BROWSER_WORKER_TOKEN are required for the competition worker."
        )
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"[:200]
    logger.info("competition.worker_started worker_id=%s", worker_id)
    while True:
        try:
            job = await repository.claim_next_kiara_job(worker_id)
        except Exception:
            logger.exception("competition.worker_claim_failed worker_id=%s", worker_id)
            if once:
                raise
            await asyncio.sleep(poll_seconds)
            continue
        if job is not None:
            try:
                await process_job(repository, client, job)
            except Exception:
                logger.exception(
                    "competition.worker_job_execution_failed worker_id=%s job_id=%s",
                    worker_id,
                    job.get("id"),
                )
                if once:
                    raise
        elif once:
            return
        else:
            await asyncio.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kiara competition durable queue worker")
    parser.add_argument("--once", action="store_true", help="claim at most one queued job, then exit")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be greater than zero")
    logging.basicConfig(
        level=os.getenv("KIARA_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_worker(once=args.once, poll_seconds=args.poll_seconds))


if __name__ == "__main__":
    main()
