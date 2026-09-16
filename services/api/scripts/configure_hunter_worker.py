"""Configure Supabase pg_cron to drain the Hunter queue every minute."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg

from apply_migrations import load_env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()
    load_env(args.env_file)
    url = os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("POSTGRES_URL")
    if not url:
        raise SystemExit("URL do PostgreSQL não configurada")
    with psycopg.connect(url, connect_timeout=10, autocommit=True) as connection:
        if not args.inspect:
            connection.execute("CREATE EXTENSION IF NOT EXISTS pg_cron")
            connection.execute("CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions")
        extensions = {row[0] for row in connection.execute(
            "SELECT extname FROM pg_extension WHERE extname IN ('pg_cron','pg_net','supabase_vault')"
        )}
        print("extensions=" + ",".join(sorted(extensions)))
        if args.inspect:
            if "pg_cron" in extensions:
                job = connection.execute(
                    "SELECT jobid,active,schedule FROM cron.job WHERE jobname='kiara-hunter-drain'"
                ).fetchone()
                print("job=" + (f"{job[0]},active={job[1]},schedule={job[2]}" if job else "missing"))
                run = connection.execute(
                    """SELECT status,return_message FROM cron.job_run_details
                       WHERE jobid=%s ORDER BY start_time DESC LIMIT 1""", (job[0],)
                ).fetchone() if job else None
                print("last_run=" + (f"{run[0]}:{run[1]}" if run else "pending"))
                response = connection.execute(
                    "SELECT status_code,timed_out,error_msg FROM net._http_response ORDER BY created DESC LIMIT 1"
                ).fetchone() if "pg_net" in extensions else None
                print("last_http=" + (f"{response[0]},timeout={response[1]},error={response[2] or 'none'}" if response else "pending"))
            return
        missing = {"pg_cron", "pg_net"} - extensions
        if missing:
            raise SystemExit("Extensões ausentes: " + ", ".join(sorted(missing)))
        secret = os.getenv("KIARA_WORKER_BOOTSTRAP_SECRET")
        if not secret:
            raise SystemExit("KIARA_WORKER_BOOTSTRAP_SECRET não informado")
        connection.execute("SELECT cron.unschedule(jobid) FROM cron.job WHERE jobname='kiara-hunter-drain'")
        command = "SELECT net.http_get(url := %s, headers := jsonb_build_object('Authorization', %s))"
        quoted_command = connection.execute(
            "SELECT format(%s, quote_literal(%s), quote_literal(%s))",
            (command, args.endpoint, f"Bearer {secret}"),
        ).fetchone()[0]
        job_id = connection.execute(
            "SELECT cron.schedule('kiara-hunter-drain', '* * * * *', %s)", (quoted_command,)
        ).fetchone()[0]
        print(f"scheduled_job_id={job_id}")


if __name__ == "__main__":
    main()
