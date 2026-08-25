from __future__ import annotations

import asyncio
import os
from typing import Any

from openai import APIError

from app.config import load_settings
from app.providers.factory import build_llm_provider
from app.providers.guarded import CircuitOpenError, CloudUsageLimitError


async def main() -> int:
    settings = load_settings()
    print("OPENAI_API_KEY carregada:", bool(os.environ.get("OPENAI_API_KEY")))

    router: Any = build_llm_provider(settings)
    fast_profile: Any = router.profiles["fast"]
    guarded: Any = fast_profile.providers[0]
    remote: Any = guarded.provider
    print("Modelo remoto:", remote.model)

    try:
        answer = await guarded.generate("Responda somente com OK.")
    except (APIError, CircuitOpenError, CloudUsageLimitError, TimeoutError) as exc:
        print("API OpenAI: FALHA")
        print("Tipo:", type(exc).__name__)
        print("HTTP status:", getattr(exc, "status_code", None))
        body = getattr(exc, "body", None)
        error = body.get("error", body) if isinstance(body, dict) else {}
        print("Código seguro:", error.get("code") if isinstance(error, dict) else None)
        return 3
    finally:
        close = getattr(remote, "aclose", None)
        if close is not None:
            await close()

    print("API OpenAI: SUCESSO")
    print("Resposta válida:", answer.strip().upper().startswith("OK"))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
