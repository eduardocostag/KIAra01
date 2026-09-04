from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.integrations.mcp import McpHub, McpServerConfig


async def verify() -> None:
    server = McpServerConfig(
        name="smoke",
        command=sys.executable,
        args=(str(ROOT / "scripts" / "mcp_smoke_server.py"),),
        allowed_tools=frozenset({"echo"}),
        timeout_seconds=10,
    )
    hub = McpHub([server])
    tools = await hub.discover("smoke")
    result = await hub.call("smoke", "echo", {"message": "MCP_OK"})
    content = str(result.get("content", ""))
    passed = tools[0]["name"] == "echo" and "MCP_OK" in content
    print(f"MCP_RUNTIME_OK={passed}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(verify())
