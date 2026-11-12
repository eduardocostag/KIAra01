"""Inspect installed runtimes without printing keys or contacting model providers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.integrations.operational_skills import OperationalSkills


def docker_engine_status() -> dict[str, object]:
    executable = shutil.which("docker")
    if not executable:
        return {"available": False, "reason": "docker_not_installed"}
    try:
        completed = subprocess.run(
            [executable, "version", "--format", "{{.Server.Version}}"],
            capture_output=True, text=True, timeout=10, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "reason": "docker_engine_unreachable"}
    if completed.returncode or not completed.stdout.strip():
        return {"available": False, "reason": "docker_engine_unreachable"}
    return {"available": True, "version": completed.stdout.strip()[:80]}


def smoke_freellmapi() -> dict[str, object]:
    service = ROOT / "services/freellmapi"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    folder = ROOT / ".tmp" / f"freellmapi-smoke-{uuid4().hex}"
    folder.mkdir(parents=True)
    env = {name: value for name, value in os.environ.items() if name.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT",
    }}
    env.update(HOST="127.0.0.1", PORT=str(port), NODE_ENV="production",
               ENCRYPTION_KEY=secrets.token_hex(32), FREEAPI_DB_PATH=str(folder / "smoke.db"),
               CLIENT_DIST=str(service / "client/dist"))
    with (folder / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(["node", str(service / "server/dist/index.js")],
                                   cwd=service, env=env, stdout=log, stderr=log)
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            url = f"http://127.0.0.1:{port}"
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError("FreeLLMAPI encerrou antes de responder; consulte log local.")
                try:
                    with opener.open(url, timeout=1) as response:
                        dashboard = response.status
                    break
                except urllib.error.URLError:
                    time.sleep(0.15)
            else:
                raise RuntimeError("FreeLLMAPI nao respondeu no prazo do smoke test.")
            try:
                opener.open(url + "/v1/models", timeout=2).close()
                protected = False
            except urllib.error.HTTPError as exc:
                protected = exc.code in {401, 403}
            if dashboard != 200 or not protected:
                raise RuntimeError("Dashboard ou protecao de autenticacao falhou.")
            return {"dashboard_status": dashboard, "models_require_auth": protected,
                    "provider_calls": 0, "process_stopped_after_check": True}
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-freellmapi", action="store_true")
    args = parser.parse_args()
    binary = ROOT / "data/tools/google-maps-scraper/google-maps-scraper.exe"
    report = {
        "skills": [entry["name"] for entry in OperationalSkills().catalog()],
        "maps_binary_installed": binary.is_file(),
        "maps_binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()
        if binary.is_file() else None,
        "freellmapi_server_built": (ROOT / "services/freellmapi/server/dist/index.js").is_file(),
        "freellmapi_dashboard_built": (ROOT / "services/freellmapi/client/dist/index.html").is_file(),
        "freellmapi_key_configured": bool(os.environ.get("FREELLMAPI_API_KEY")),
        "chatwoot_checkout_present": (ROOT / "services/chatwoot/Gemfile").is_file(),
        "chatwoot_docker_available": shutil.which("docker") is not None,
        "chatwoot_docker_engine": docker_engine_status(),
        "chatwoot_token_configured": bool(os.environ.get("CHATWOOT_API_ACCESS_TOKEN")),
    }
    if args.smoke_freellmapi:
        report["freellmapi_smoke"] = smoke_freellmapi()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
