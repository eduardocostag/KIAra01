from __future__ import annotations

import json
import sys


def respond(identifier, result) -> None:
    print(
        json.dumps({"jsonrpc": "2.0", "id": identifier, "result": result}),
        flush=True,
    )


for line in sys.stdin:
    try:
        request = json.loads(line)
    except json.JSONDecodeError:
        continue
    identifier = request.get("id")
    method = request.get("method")
    if identifier is None:
        continue
    if method == "initialize":
        respond(
            identifier,
            {
                "protocolVersion": request.get("params", {}).get(
                    "protocolVersion", "2025-06-18"
                ),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "kiara-smoke", "version": "1.0"},
            },
        )
    elif method == "tools/list":
        respond(
            identifier,
            {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Returns bounded local text for runtime verification.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"message": {"type": "string"}},
                            "required": ["message"],
                            "additionalProperties": False,
                        },
                    }
                ]
            },
        )
    elif method == "tools/call":
        message = str(request.get("params", {}).get("arguments", {}).get("message", ""))
        respond(
            identifier,
            {"content": [{"type": "text", "text": message[:100]}], "isError": False},
        )
    else:
        print(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": identifier,
                    "error": {"code": -32601, "message": "Method not found"},
                }
            ),
            flush=True,
        )
