"""Explainable commercial prioritisation from observed message evidence."""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def qualify_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    incoming = [str(item.get("text", item.get("body", ""))) for item in messages
                if item.get("direction") in {"inbound", "in"}][-8:]
    text = unicodedata.normalize("NFKD", " ".join(incoming).casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'"[^"\n]*"|“[^”\n]*”', "", text)
    reasons = []
    score = 10 if incoming else 0
    signals = [
        (r"\b(orcamento|preco|valor|quanto custa|proposta)\b", 25, "Solicitou preço ou proposta"),
        (r"\b(quero contratar|quero comprar|fechar|contratar|comprar)\b", 35, "Expressou intenção de compra"),
        (r"\b(hoje|amanha|urgente|esta semana|agendar|reuniao)\b", 20, "Indicou prazo ou próximo compromisso"),
        (r"\b(interesse|interessado|preciso|necessito|gostaria)\b", 15, "Descreveu interesse ou necessidade"),
    ]
    for pattern, points, reason in signals:
        matches = list(re.finditer(pattern, text))
        positive = any(not re.search(r"\b(nao|sem|nunca|nem)\b[^.!?;\n]{0,45}$", text[max(0, match.start()-50):match.start()]) for match in matches)
        if positive:
            score += points
            reasons.append(reason)
    optout = bool(re.search(r"\b(nao tenho interesse|sem interesse|pare de|nao me envie|remova meu|sair)\b", text))
    handoff = bool(re.search(r"\b(atendente|falar com humano|pessoa de verdade|falar com uma pessoa)\b", text))
    latest = unicodedata.normalize("NFKD", incoming[-1].casefold()) if incoming else ""
    latest = "".join(c for c in latest if not unicodedata.combining(c))
    latest = re.sub(r'"[^"\n]*"|“[^”\n]*”', "", latest)
    if re.search(r"\b(nao (?:quero|vou|posso) (?:comprar|contratar|fechar)|sem (?:orcamento|verba)|nao tenho (?:orcamento|verba))\b", latest):
        score = min(score, 10)
        reasons = ["Mensagem recente nega intenção de compra ou disponibilidade de orçamento"]
    if optout:
        score = 0
        reasons = ["Contato pediu interrupção ou informou falta de interesse"]
    if not reasons:
        reasons = ["Ainda não há sinal explícito de intenção comercial"]
    score = min(100, score)
    temperature = "hot" if score >= 65 else "warm" if score >= 35 else "cold"
    next_action = "Não contatar; respeitar pedido de interrupção" if optout else (
        "Transferir para atendimento humano" if handoff else
        "Preparar proposta e confirmar próximo passo" if score >= 65 else
        "Entender necessidade e qualificar oportunidade" if score >= 35 else
        "Perguntar necessidade e contexto antes de ofertar"
    )
    return {"score": score, "temperature": temperature, "reasons": reasons,
            "confidence": round(min(0.95, 0.35 + len(incoming) * 0.04 + len(reasons) * 0.08), 2),
            "recommendation": next_action, "optout": optout, "handoff": handoff,
            "stage": "opportunity" if score >= 65 else "qualified" if score >= 35 else "contacted"}
