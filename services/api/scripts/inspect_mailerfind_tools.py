"""List MailerFind MCP tool contracts without printing credentials or customer data."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

import psycopg
from cryptography.fernet import Fernet


def load_env(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def rpc(endpoint: str, token: str, payload: dict[str, object], session_id: str | None = None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = Request(endpoint, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urlopen(request, timeout=20) as response:
        body = response.read(1_000_000).decode("utf-8")
        returned_session = response.headers.get("Mcp-Session-Id") or session_id
    if body.startswith("event:") or "\ndata:" in body:
        lines = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")]
        body = lines[-1]
    return json.loads(body) if body else {}, returned_session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    args = parser.parse_args()
    load_env(args.env_file)
    database_url = os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    encryption_key = os.getenv("KIARA_INTEGRATION_ENCRYPTION_KEY")
    if not database_url or not encryption_key:
        raise SystemExit("Database or integration encryption configuration is missing")
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        row = connection.execute(
            "SELECT encrypted_credentials FROM integration_credentials WHERE provider='mailerfind' AND is_global=true AND status!='disabled' LIMIT 1"
        ).fetchone()
    if not row:
        raise SystemExit("Global MailerFind integration is not configured")
    credentials = json.loads(Fernet(encryption_key.encode()).decrypt(row[0].encode()))
    endpoint, token = credentials["endpoint_url"], credentials["access_token"]
    _, session_id = rpc(endpoint, token, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "Kiara diagnostics", "version": "1.0"},
        },
    })
    rpc(endpoint, token, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, session_id)
    result, _ = rpc(endpoint, token, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, session_id)
    tools = result.get("result", {}).get("tools", [])
    print(json.dumps([
        {"name": item.get("name"), "description": item.get("description"), "inputSchema": item.get("inputSchema")}
        for item in tools
    ], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
