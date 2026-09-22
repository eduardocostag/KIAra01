"""Exercise Hunter across every Brazilian state using aggregate, read-only evidence.

This script calls the same research orchestration used by production, but never
writes searches, leads, pipeline entries, or messages to the database.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from apply_migrations import load_env
from kiara_api.hunter import SearchCreate, execute_research


CASES = [
    ("AC", "Rio Branco", "dentistas", 5),
    ("AL", "Maceió", "clínicas de estética", 10),
    ("AP", "Macapá", "escritórios de contabilidade", 20),
    ("AM", "Manaus", "advogados trabalhistas", 30),
    ("BA", "Salvador", "escolas de idiomas", 50),
    ("CE", "Fortaleza", "personal trainers", 80),
    ("DF", "Brasília", "agências de marketing", 100),
    ("ES", "Vitória", "clínicas odontológicas", 5),
    ("GO", "Goiânia", "imobiliárias", 10),
    ("MA", "São Luís", "pediatras", 20),
    ("MT", "Cuiabá", "oficinas mecânicas", 30),
    ("MS", "Campo Grande", "fisioterapeutas", 50),
    ("MG", "Belo Horizonte", "psicólogos", 80),
    ("PA", "Belém", "arquitetos", 100),
    ("PB", "João Pessoa", "nutricionistas", 5),
    ("PR", "Curitiba", "educadores físicos", 10),
    ("PE", "Recife", "restaurantes veganos", 20),
    ("PI", "Teresina", "veterinários", 30),
    ("RJ", "Rio de Janeiro", "dermatologistas", 50),
    ("RN", "Natal", "fotógrafos", 80),
    ("RS", "Porto Alegre", "dentistas", 100),
    ("RO", "Porto Velho", "corretores de seguros", 5),
    ("RR", "Boa Vista", "salões de beleza", 10),
    ("SC", "Florianópolis", "desenvolvedores de software", 20),
    ("SP", "São Paulo", "psiquiatras", 30),
    ("SE", "Aracaju", "engenheiros civis", 50),
    ("TO", "Palmas", "consultorias empresariais", 80),
]

SOURCES = ["web", "google_maps", "instagram", "facebook"]


async def run_case(case: tuple[str, str, str, int], gate: asyncio.Semaphore) -> dict[str, object]:
    state, city, profession, limit = case
    payload = SearchCreate(
        market="b2b", query=profession, location=f"{city} - {state}",
        sources=SOURCES, result_limit=limit,
    ).model_dump()
    started = time.monotonic()
    async with gate:
        try:
            outcome = await execute_research(payload)
            counts = Counter(row.get("source", "unknown") for row in outcome["results"])
            return {
                "state": state, "city": city, "profession": profession, "limit": limit,
                "status": "ok" if outcome.get("error") is None else "provider_error",
                "error": outcome.get("error"), "accepted": len(outcome["results"]),
                "source_failures": outcome["validation"]["source_failures"],
                "by_source": dict(counts), "warnings": len(outcome.get("warnings", [])),
                "seconds": round(time.monotonic() - started, 2),
            }
        except Exception as exc:  # noqa: BLE001 - the matrix must report every case
            return {
                "state": state, "city": city, "profession": profession, "limit": limit,
                "status": "exception", "error": type(exc).__name__, "accepted": 0,
                "source_failures": len(SOURCES), "by_source": {}, "warnings": 0,
                "seconds": round(time.monotonic() - started, 2),
            }


async def main_async(concurrency: int, selected_state: str | None) -> int:
    gate = asyncio.Semaphore(concurrency)
    cases = [case for case in CASES if selected_state is None or case[0] == selected_state.upper()]
    if not cases:
        raise SystemExit(f"UF desconhecida: {selected_state}")
    tasks = [asyncio.create_task(run_case(case, gate)) for case in cases]
    rows: list[dict[str, object]] = []
    for task in asyncio.as_completed(tasks):
        row = await task
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    summary = {
        "states": len(rows),
        "ok": sum(row["status"] == "ok" for row in rows),
        "provider_errors": sum(row["status"] == "provider_error" for row in rows),
        "exceptions": sum(row["status"] == "exception" for row in rows),
        "empty": sum(int(row["accepted"]) == 0 for row in rows),
        "accepted_total": sum(int(row["accepted"]) for row in rows),
        "source_failures": sum(int(row["source_failures"]) for row in rows),
    }
    print("SUMMARY=" + json.dumps(summary, ensure_ascii=False), flush=True)
    return 1 if summary["provider_errors"] or summary["exceptions"] or summary["source_failures"] else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=1, choices=range(1, 5))
    parser.add_argument("--state")
    args = parser.parse_args()
    load_env(args.env_file)
    raise SystemExit(asyncio.run(main_async(args.concurrency, args.state)))


if __name__ == "__main__":
    main()
