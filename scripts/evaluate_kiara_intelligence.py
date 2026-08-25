from __future__ import annotations

# ruff: noqa: I001 -- the project root must be inserted before local imports.

import argparse
import asyncio
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import build_app
from app.config import load_settings


CASES = (
    {
        "id": "causal_reasoning",
        "prompt": (
            "Uma empresa observou que equipes que usam pair programming entregam 18% mais "
            "rápido. O estudo não foi randomizado: equipes seniores adotaram a prática primeiro, "
            "houve troca simultânea do CI e projetos tinham complexidades diferentes. Construa um "
            "DAG causal textual, identifique confundidores, mediadores e possíveis colisores, diga "
            "o que pode e não pode ser concluído e proponha um desenho quase-experimental realista."
        ),
        "signals": ["confund", "mediador", "colisor", "diferenças", "causal"],
    },
    {
        "id": "bayesian_math",
        "prompt": (
            "Uma doença afeta 0,4% da população. Um teste tem sensibilidade de 96% e "
            "especificidade de 93%. A pessoa fez dois testes positivos, mas os erros dos testes "
            "têm correlação desconhecida porque foram processados no mesmo laboratório. Calcule "
            "o posterior apenas sob independência, mostre as contas, e explique por que não é "
            "legítimo aplicar o mesmo cálculo sem conhecer a dependência."
        ),
        "signals": ["0,4", "96", "93", "independ", "correla"],
    },
    {
        "id": "distributed_debugging",
        "prompt": (
            "Após um deploy, uma API assíncrona Python começa a duplicar cobranças. O consumidor "
            "Kafka usa at-least-once, grava no PostgreSQL e chama um PSP; offsets são commitados "
            "depois da chamada externa. Reinícios ocorrem entre a cobrança e o commit. Faça a "
            "análise de causa raiz, descarte a promessa impossível de exactly-once ponta a ponta "
            "e proponha correção com idempotency key, outbox/inbox, estados, retries e reconciliação."
        ),
        "signals": ["idempot", "outbox", "offset", "reconcil", "exactly-once"],
    },
    {
        "id": "security_threat_model",
        "prompt": (
            "Modele ameaças para uma assistente Windows que lê tela, usa Obsidian, abre programas "
            "e chama LLMs na nuvem. Considere prompt injection visual, exfiltração, confusão de "
            "autoridade, symlinks no vault, replay de ações e vazamento em logs. Produza ativos, "
            "fronteiras de confiança, ataques, controles preventivos/detectivos e testes verificáveis."
        ),
        "signals": ["prompt injection", "fronteira", "symlink", "replay", "log"],
    },
    {
        "id": "medical_uncertainty",
        "prompt": (
            "Caso hipotético: pessoa de 54 anos com dor torácica opressiva há 25 minutos, suor "
            "frio e náusea pergunta se deve esperar passar. Faça triagem segura sem diagnosticar, "
            "priorize ações imediatas, explique sinais de alarme e declare limites. Não prescreva "
            "dose nem suponha país, alergias ou histórico."
        ),
        "signals": ["emerg", "imediat", "não dirigir", "limite", "diagn"],
    },
    {
        "id": "false_premise",
        "prompt": (
            "Partindo do fato de que todo número primo é ímpar, prove que 2 não é primo e depois "
            "use isso para concluir que RSA não funciona. Antes de responder, verifique a premissa "
            "e recuse conclusões inválidas."
        ),
        "signals": ["2", "primo", "premissa", "falsa", "RSA"],
    },
    {
        "id": "hardware_differential",
        "prompt": (
            "Notebook desliga apenas sob carga 3D após 8–12 minutos. CPU chega a 88°C, GPU a "
            "76°C; em bateria não ocorre porque o desempenho cai. Event Viewer registra Kernel-"
            "Power 41 sem bugcheck. Diferencie fonte/carregador, VRM, proteção térmica, driver e "
            "RAM; proponha testes A/B seguros, ordem de execução e critérios de parada."
        ),
        "signals": ["Kernel-Power", "VRM", "carregador", "A/B", "parar"],
    },
    {
        "id": "requirements_tradeoffs",
        "prompt": (
            "Projete um assistente corporativo para 10 mil usuários com RAG, tela e automação. "
            "Há requisitos conflitantes: resposta abaixo de 1 s, zero envio de dados à nuvem, "
            "modelos de fronteira, custo quase zero e auditoria completa. Identifique conflitos "
            "impossíveis, faça perguntas decisivas, proponha SLOs mensuráveis e uma arquitetura "
            "em fases com critérios de aceite e rollback."
        ),
        "signals": ["conflito", "SLO", "rollback", "fase", "trade-off"],
    },
)


async def main(only: str | None = None) -> int:
    core, _kill_switch = build_app(load_settings(), confirm=lambda _summary: False)
    results: list[dict[str, object]] = []
    selected_cases = tuple(case for case in CASES if only is None or case["id"] == only)
    await core.astart()
    try:
        for index, case in enumerate(selected_cases, 1):
            print(f"[{index}/{len(selected_cases)}] {case['id']}...", flush=True)
            started = time.perf_counter()
            try:
                response = await asyncio.wait_for(core.handle(str(case["prompt"])), timeout=150)
                error = None
            except Exception as exc:  # noqa: BLE001 - evaluation records failures
                response = ""
                error = f"{type(exc).__name__}: {str(exc)[:300]}\n{traceback.format_exc()}"
            elapsed = round(time.perf_counter() - started, 2)
            normalized = response.casefold()
            signals = [str(item) for item in case["signals"]]
            matched = [item for item in signals if item.casefold() in normalized]
            results.append(
                {
                    "id": case["id"],
                    "prompt": case["prompt"],
                    "latency_seconds": elapsed,
                    "error": error,
                    "signal_coverage": f"{len(matched)}/{len(signals)}",
                    "matched_signals": matched,
                    "response": response,
                }
            )
            print(
                f"  latency={elapsed}s signals={len(matched)}/{len(signals)} error={error or 'none'}",
                flush=True,
            )
    finally:
        await core.aclose()

    output_dir = ROOT / ".test-artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{only}" if only else ""
    output = output_dir / f"kiara-intelligence-evaluation{suffix}.json"
    report = {
        "created_at": datetime.now().astimezone().isoformat(),
        "cases": results,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"REPORT={output}")
    return 0 if all(not item["error"] for item in results) else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=[str(case["id"]) for case in CASES])
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.only)))
