"""Create and immediately release one Browserbase session, printing no secrets."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from apply_migrations import load_env
from browserbase import Browserbase


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    load_env(args.env_file)
    key = os.getenv("BROWSERBASE_API_KEY", "")
    project = os.getenv("BROWSERBASE_PROJECT_ID", "")
    if not key or not project:
        raise SystemExit("browserbase_configuration=missing")
    client = Browserbase(api_key=key, timeout=10, max_retries=0)
    try:
        session = client.sessions.create(project_id=project, keep_alive=False)
        print("browserbase_session=create_ok")
        client.sessions.update(session.id, project_id=project, status="REQUEST_RELEASE", timeout=4)
        print("browserbase_session=release_ok")
    except Exception as error:
        status = getattr(error, "status_code", None)
        code = getattr(error, "code", None)
        print(
            f"browserbase_session=failed error_type={type(error).__name__} "
            f"status={status} code={code}"
        )
        raise SystemExit(1) from error
    finally:
        client.close()


if __name__ == "__main__":
    main()
