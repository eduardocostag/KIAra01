"""Run a diverse, non-PII live Hunter provider matrix and print only aggregate evidence."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from apply_migrations import load_env
from kiara_api.hunter import SearchCreate, execute_research

CASES = [
    ("odontologia_sul", "dentistas e clínicas odontológicas", "Porto Alegre - RS", ["google_maps", "web", "instagram"], 10),
    ("saude_sudeste", "psiquiatras", "São Paulo - SP", ["google_maps", "web"], 20),
    ("fitness_nordeste", "educadores físicos e personal trainers", "Recife - PE", ["google_maps", "instagram"], 10),
    ("marketing_sul", "agências de marketing digital", "Curitiba - PR", ["web", "linkedin"], 20),
    ("estetica_sudeste", "clínicas de estética", "Belo Horizonte - MG", ["google_maps", "web", "instagram"], 30),
    ("alimentacao_sul", "restaurantes veganos", "Florianópolis - SC", ["google_maps", "web"], 15),
    ("contabilidade_centro", "escritórios de contabilidade", "Goiânia - GO", ["google_maps", "web", "linkedin"], 10),
    ("educacao_nordeste", "escolas de idiomas", "Salvador - BA", ["google_maps", "web", "instagram"], 15),
    ("juridico_norte", "advogados trabalhistas", "Manaus - AM", ["google_maps", "web"], 5),
    ("automotivo_sudeste", "oficinas mecânicas", "Campinas - SP", ["google_maps", "web"], 50),
    ("automotivo_sudeste_maps", "oficinas mecânicas", "Campinas - SP", ["google_maps"], 50),
    ("automotivo_sudeste_web", "oficinas mecânicas", "Campinas - SP", ["web"], 50),
]


async def run_case(case: tuple[str, str, str, list[str], int], gate: asyncio.Semaphore) -> dict[str, object]:
    name, query, location, sources, limit = case
    payload = SearchCreate(market="b2b", query=query, location=location, sources=sources,
                           result_limit=limit).model_dump()
    started = time.monotonic()
    async with gate:
        try:
            outcome = await execute_research(payload)
            return {
                "case": name, "location": location, "sources": sources, "limit": limit,
                "status": "ok" if not outcome.get("error") else "retryable",
                "error": outcome.get("error"),
                "accepted": outcome.get("validation", {}).get("accepted", 0),
                "checked": outcome.get("validation", {}).get("checked", 0),
                "source_failures": outcome.get("validation", {}).get("source_failures", 0),
                "warnings": len(outcome.get("warnings", [])),
                "warning_details": outcome.get("warnings", []),
                "elapsed_seconds": round(time.monotonic() - started, 2),
            }
        except Exception as exc:  # noqa: BLE001 - matrix must report every boundary failure
            return {"case": name, "location": location, "sources": sources, "limit": limit,
                    "status": "exception", "error": type(exc).__name__, "accepted": 0,
                    "checked": 0, "source_failures": len(sources), "warnings": 0,
                    "elapsed_seconds": round(time.monotonic() - started, 2)}


async def main_async(selected: str | None) -> int:
    gate = asyncio.Semaphore(2)
    cases = [case for case in CASES if selected is None or case[0] == selected]
    if not cases:
        raise SystemExit(f"Caso desconhecido: {selected}")
    rows = await asyncio.gather(*(run_case(case, gate) for case in cases))
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    summary = {
        "cases": len(rows), "ok": sum(row["status"] == "ok" for row in rows),
        "retryable": sum(row["status"] == "retryable" for row in rows),
        "exceptions": sum(row["status"] == "exception" for row in rows),
        "accepted_total": sum(int(row["accepted"]) for row in rows),
        "source_failures": sum(int(row["source_failures"]) for row in rows),
    }
    print("SUMMARY=" + json.dumps(summary, ensure_ascii=False))
    return 1 if summary["exceptions"] else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--case")
    args = parser.parse_args()
    load_env(args.env_file)
    raise SystemExit(asyncio.run(main_async(args.case)))


if __name__ == "__main__":
    main()
