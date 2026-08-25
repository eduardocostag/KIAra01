from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import load_settings
from app.providers.factory import _build_provider


async def main() -> int:
    settings = load_settings()
    candidates = settings.get("llm.routing.fast.candidates", [])
    prompt = "Responda em português, em no máximo duas frases: qual é a função de um ledger de dupla entrada?"
    failures = 0
    for candidate in candidates:
        provider_name = str(candidate.get("provider", ""))
        model = str(candidate.get("model", ""))
        started = time.perf_counter()
        try:
            provider = _build_provider(provider_name, settings, os.environ, 25.0, model)
            answer = await asyncio.wait_for(provider.generate(prompt), timeout=30.0)
        except Exception as exc:  # noqa: BLE001 - diagnostic boundary
            failures += 1
            elapsed = time.perf_counter() - started
            print(f"FALHA | {model} | {elapsed:.1f}s | {type(exc).__name__}: {str(exc)[:180]}")
        else:
            elapsed = time.perf_counter() - started
            print(f"OK | {model} | {elapsed:.1f}s | resposta={bool(answer.strip())}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
