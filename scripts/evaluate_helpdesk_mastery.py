from __future__ import annotations

# ruff: noqa: I001 -- project root must be available before local imports.

import asyncio
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import build_app
from app.config import load_settings


CASES = (
    ("subnet", "Para 192.168.10.130/26, informe rede, broadcast e faixa utilizável, mostrando como chegou ao resultado.", ("192.168.10.128", "192.168.10.191", "192.168.10.129", "192.168.10.190")),
    ("bandwidth", "Uma conexão de 1 Gbps transfere quantos MB/s em teoria e por que o valor real é menor?", ("125", "8", "overhead")),
    ("apipa", "Um Windows recebeu 169.254.17.8. Explique o que isso prova, o que não prova e dê uma sequência de testes.", ("apipa", "dhcp", "ipconfig", "cabo")),
    ("dns", "O PC pinga 8.8.8.8, mas não resolve google.com. Diagnostique por hipóteses e testes, sem assumir que é apenas cache.", ("dns", "nslookup", "53", "servidor")),
    ("localhost", "Um serviço funciona em localhost:8080, mas não em outra máquina. Dê hipóteses, comandos e interpretação dos resultados.", ("127.0.0.1", "firewall", "get-nettcpconnection", "test-netconnection")),
    ("backup", "Compare RAID, snapshot e backup e proponha proteção para um servidor crítico contra falha, exclusão e ransomware.", ("raid", "snapshot", "3-2-1", "imut")),
    ("rpo_rto", "O negócio aceita perder 15 minutos de dados e precisa voltar em até 2 horas. Defina RPO/RTO e traduza isso em controles testáveis.", ("rpo", "15", "rto", "2 horas")),
    ("rmm", "Um script PowerShell funciona no console do usuário e falha no RMM como SYSTEM. Monte diagnóstico diferencial e testes.", ("system", "perfil", "mapead", "32")),
    ("ransomware", "Uma estação corporativa mostra ransomware ativo. Ordene as ações imediatas e explique o que não fazer.", ("isol", "rede", "incidente", "evid")),
    ("database", "Uma consulta passou de 100 ms para 30 s quando a tabela cresceu de 10 mil para 10 milhões de linhas. Como investigar antes de criar índices?", ("plano", "explain", "estat", "bloque")),
    ("rag", "Uma IA responde bem quando acha documentos e inventa quando não acha. Proponha correção verificável e diferencie RAG de fine-tuning.", ("rag", "limiar", "fonte", "fine-tuning")),
    ("firewall", "Depois da troca do firewall, ping e internet funcionam, mas sistemas internos não. Crie diagnóstico por camadas com critérios de decisão.", ("porta", "regra", "nat", "log")),
)


async def main(only: set[str] | None = None) -> int:
    core, _ = build_app(load_settings(), confirm=lambda _summary: False)
    results = []
    await core.astart()
    try:
        selected = tuple(case for case in CASES if only is None or case[0] in only)
        for index, (case_id, prompt, signals) in enumerate(selected, 1):
            print(f"[{index}/{len(selected)}] {case_id}", flush=True)
            started = time.perf_counter()
            try:
                # Evaluate intelligence in isolation: production conversation history and the
                # feedback prompt must not contaminate benchmark answers or user data.
                response = await asyncio.wait_for(
                    core.agent_router.respond(
                        prompt,
                        {
                            "user_message": prompt,
                            "assistant_capabilities": {
                                "platform": "Windows",
                                "mode": "consultive_read_only",
                            },
                        },
                    ),
                    timeout=150,
                )
                error = None
            except Exception as exc:  # noqa: BLE001 - benchmark records failures
                response, error = "", f"{type(exc).__name__}: {exc}"
            normalized = response.casefold()
            matched = [signal for signal in signals if signal.casefold() in normalized]
            results.append({
                "id": case_id,
                "prompt": prompt,
                "latency_seconds": round(time.perf_counter() - started, 2),
                "coverage": f"{len(matched)}/{len(signals)}",
                "matched": matched,
                "error": error,
                "response": response,
            })
            print(f"  coverage={len(matched)}/{len(signals)} error={error or 'none'}", flush=True)
    finally:
        await core.aclose()
    output = ROOT / ".test-artifacts" / "helpdesk-mastery-evaluation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"created_at": datetime.now().astimezone().isoformat(), "cases": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"REPORT={output}")
    return 0 if all(not item["error"] for item in results) else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(set(args.only) if args.only else None)))
