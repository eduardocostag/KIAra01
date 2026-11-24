"""Configurar atendimento: the client says what the business is, sells and charges, and how Kiara should attend.

What the client fills in always wins. The chosen niche fills the gaps with how that market is attended (what to
find out, where to lead the conversation, when to call a person, what never to say), so a client who writes little
still gets a good attendant on day one. Stored in sales_profiles.service (migration 0038), one per workspace.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .adapters.postgres import PostgresRepository, _iso, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError

GOALS: dict[str, str] = {
    "schedule": "agendar uma avaliação, consulta ou atendimento",
    "visit": "marcar uma visita",
    "quote": "enviar um orçamento",
    "sale": "fechar a venda pelo WhatsApp",
    "handoff": "passar o contato para um vendedor da equipe",
}

# How each market is attended. `examples` only fill the form's placeholders; `care` always goes to the AI.
NICHES: dict[str, dict[str, Any]] = {
    "odontologia": {
        "label": "Odontologia", "goal": "schedule", "payment_label": "Convênios e formas de pagamento",
        "discover": ["Qual tratamento procura ou o que está incomodando", "Se tem dor ou é urgente", "Convênio ou particular", "Melhor dia e horário"],
        "handoff": "Dor forte ou urgência, pedido de orçamento de tratamento completo, reclamação ou dúvida clínica.",
        "care": "Siga o código de ética odontológico: não anuncie promoções nem descontos e não dê diagnóstico ou indique tratamento pelo WhatsApp; o caminho é a avaliação com o dentista.",
        "examples": [["Avaliação", "R$ 100"], ["Limpeza", "R$ 180"], ["Clareamento", "a partir de R$ 900"]],
    },
    "estetica": {
        "label": "Estética e beleza", "goal": "schedule", "payment_label": "Formas de pagamento e pacotes",
        "discover": ["Qual procedimento ou resultado procura", "Se já fez antes", "Melhor dia e horário"],
        "handoff": "Dúvida sobre contraindicação ou saúde, reação a um procedimento, reclamação ou negociação de pacote.",
        "care": "Não prometa resultados garantidos nem dê orientação de saúde; contraindicações são avaliadas pela profissional.",
        "examples": [["Limpeza de pele", "R$ 150"], ["Design de sobrancelha", "R$ 60"], ["Pacote 5 sessões", "R$ 600"]],
    },
    "saude": {
        "label": "Clínica e saúde", "goal": "schedule", "payment_label": "Convênios e formas de pagamento",
        "discover": ["Especialidade ou motivo da consulta", "Convênio ou particular", "Se é urgente", "Melhor dia e horário"],
        "handoff": "Sintoma grave ou urgência (oriente procurar um pronto-socorro), dúvida clínica, resultado de exame ou reclamação.",
        "care": "Nunca dê diagnóstico, orientação médica ou opinião sobre remédios; em sinais de urgência, oriente procurar atendimento de emergência.",
        "examples": [["Consulta", "R$ 250"], ["Retorno", "sem custo em até 30 dias"], ["Sessão de fisioterapia", "R$ 120"]],
    },
    "imobiliaria": {
        "label": "Imobiliária e corretores", "goal": "visit", "payment_label": "Financiamento, permuta e condições",
        "discover": ["Comprar ou alugar", "Bairro ou região", "Faixa de preço", "Quartos e vagas", "Se vai financiar"],
        "handoff": "Pedido de proposta, negociação de valor, documentação, análise de crédito ou visita confirmada.",
        "care": "Valores são referência e podem mudar; nunca prometa aprovação de financiamento nem disponibilidade sem confirmar.",
        "examples": [["Apartamento 2 quartos no Centro", "R$ 420 mil"], ["Aluguel casa 3 quartos", "R$ 2.800/mês"], ["Avaliação do seu imóvel", "sem custo"]],
    },
    "advocacia": {
        "label": "Advocacia", "goal": "schedule", "payment_label": "Honorários e formas de pagamento",
        "discover": ["Área do problema (trabalhista, família, consumidor…)", "Se há prazo ou audiência marcada", "Melhor horário para a consulta"],
        "handoff": "Qualquer pedido de opinião sobre o caso, prazo ou audiência próxima, ou pedido de proposta de honorários.",
        "care": "Não dê parecer jurídico nem garanta resultado; siga as regras da OAB e não faça captação agressiva; o caminho é a consulta com o advogado.",
        "examples": [["Consulta inicial", "R$ 300"], ["Revisão de contrato", "a partir de R$ 500"]],
    },
    "contabilidade": {
        "label": "Contabilidade", "goal": "quote", "payment_label": "Formas de pagamento",
        "discover": ["Tipo de empresa (MEI, Simples, Lucro Presumido)", "Se está abrindo ou trocando de contador", "Número de funcionários", "Faturamento aproximado"],
        "handoff": "Pedido de proposta fechada, empresa com pendências fiscais ou dúvida tributária específica.",
        "care": "Não dê orientação tributária definitiva pelo WhatsApp; valores dependem do porte e do regime da empresa.",
        "examples": [["Abertura de empresa", "a partir de R$ 800"], ["Mensalidade Simples Nacional", "a partir de R$ 350"]],
    },
    "academia": {
        "label": "Academia e estúdio", "goal": "schedule", "payment_label": "Planos e formas de pagamento",
        "discover": ["Objetivo (emagrecer, ganhar massa, saúde)", "Horário que pretende treinar", "Se já treina"],
        "handoff": "Restrição de saúde ou lesão, cancelamento de plano, cobrança ou reclamação.",
        "care": "Não prescreva treino nem dieta pelo WhatsApp; restrições de saúde são avaliadas pelo profissional.",
        "examples": [["Plano mensal", "R$ 119"], ["Plano anual", "R$ 89/mês"], ["Aula experimental", "grátis"]],
    },
    "oficina": {
        "label": "Oficina e autopeças", "goal": "quote", "payment_label": "Formas de pagamento",
        "discover": ["Modelo e ano do veículo", "O que está acontecendo com o carro", "Se o carro está rodando", "Melhor dia para trazer"],
        "handoff": "Orçamento que depende de diagnóstico, garantia de serviço ou reclamação.",
        "care": "Não feche preço de conserto sem diagnóstico; dê só valores de serviços fixos (troca de óleo, revisão).",
        "examples": [["Troca de óleo", "a partir de R$ 180"], ["Alinhamento e balanceamento", "R$ 120"], ["Diagnóstico", "R$ 90"]],
    },
    "educacao": {
        "label": "Cursos e escolas", "goal": "schedule", "payment_label": "Mensalidades, bolsas e formas de pagamento",
        "discover": ["Curso ou série de interesse", "Para quem é (a própria pessoa ou um filho)", "Turno preferido", "Quando quer começar"],
        "handoff": "Pedido de bolsa ou desconto, matrícula, transferência ou reclamação.",
        "care": "Não garanta vaga nem aprovação; condições de bolsa são definidas pela secretaria.",
        "examples": [["Mensalidade curso de inglês", "R$ 290"], ["Matrícula", "R$ 150"], ["Aula experimental", "grátis"]],
    },
    "servicos": {
        "label": "Serviços para empresas", "goal": "quote", "payment_label": "Formas de pagamento",
        "discover": ["O que a empresa precisa resolver", "Prazo", "Orçamento aproximado", "Quem decide"],
        "handoff": "Pedido de proposta personalizada, negociação de valor ou reunião com o responsável.",
        "care": "Não prometa prazos ou resultados que dependem de análise do projeto.",
        "examples": [["Site institucional", "a partir de R$ 1.500"], ["Gestão de redes sociais", "R$ 900/mês"]],
    },
    "varejo": {
        "label": "Loja e varejo", "goal": "sale", "payment_label": "Formas de pagamento, entrega e trocas",
        "discover": ["Qual produto procura", "Tamanho, cor ou modelo", "Se quer entrega ou retirada"],
        "handoff": "Troca ou devolução, problema com pedido, pedido grande ou reclamação.",
        "care": "Não confirme estoque nem prazo de entrega sem ter a informação.",
        "examples": [["Camiseta básica", "R$ 59"], ["Frete na cidade", "R$ 10"]],
    },
}


class ServiceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    price: str = Field(default="", max_length=60)


class ServiceSetup(BaseModel):
    """Everything is optional: whatever is missing comes from the niche, or Kiara says she will check."""
    model_config = ConfigDict(extra="forbid")
    niche: str = Field(default="", max_length=40, pattern=r"^[a-z_]*$")
    niche_other: str = Field(default="", max_length=80)
    services: list[ServiceItem] = Field(default_factory=list, max_length=40)
    hide_prices: bool = False
    hours: str = Field(default="", max_length=300)
    address: str = Field(default="", max_length=300)
    payment: str = Field(default="", max_length=500)
    goal: Literal["", "schedule", "visit", "quote", "sale", "handoff"] = ""
    goal_detail: str = Field(default="", max_length=300)
    discover: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(default_factory=list, max_length=12)
    handoff: str = Field(default="", max_length=600)
    tone: Literal["", "formal", "friendly"] = ""
    emojis: bool = True
    never_say: str = Field(default="", max_length=600)
    extra: str = Field(default="", max_length=4000)


def stored_setup(raw: Any) -> ServiceSetup:
    """A stored setup, tolerant of fields an older or newer version wrote."""
    if not isinstance(raw, dict):
        return ServiceSetup()
    fields = ServiceSetup.model_fields
    try:
        return ServiceSetup.model_validate({key: value for key, value in raw.items() if key in fields})
    except ValueError:
        return ServiceSetup()


def is_configured(setup: ServiceSetup) -> bool:
    return bool(setup.niche or setup.niche_other.strip() or setup.services or setup.extra.strip())


def service_block(raw: Any) -> str:
    """The attendance setup as instructions for every Kiara prompt (data from the client, never instructions to
    obey beyond how to attend). Empty when nothing was configured."""
    setup = raw if isinstance(raw, ServiceSetup) else stored_setup(raw)
    if not is_configured(setup) and not any((setup.hours, setup.address, setup.payment, setup.goal, setup.handoff)):
        return ""
    niche = NICHES.get(setup.niche, {})
    label = setup.niche_other.strip() if setup.niche == "outro" or not niche else niche["label"]
    lines = ["Configuração do atendimento (definida pela empresa; tem prioridade sobre o resto):"]
    if label:
        lines.append(f"Nicho: {label}.")
    if setup.services:
        lines.append("Serviços e produtos" + (":" if not setup.hide_prices else " (sem preço pelo WhatsApp):"))
        for item in setup.services:
            price = item.price.strip()
            lines.append(f"- {item.name.strip()}" + (f": {price}" if price and not setup.hide_prices else "" if setup.hide_prices else ": valor sob consulta"))
    if setup.hide_prices:
        lines.append("Não informe preços pelo WhatsApp: explique com naturalidade que o valor depende do caso e convide para o próximo passo.")
    for title, value in (("Horário de atendimento", setup.hours), ("Endereço", setup.address),
                         (niche.get("payment_label", "Pagamento e condições"), setup.payment)):
        if value.strip():
            lines.append(f"{title}: {value.strip()}")
    goal = setup.goal or niche.get("goal", "")
    if goal:
        lines.append(f"Objetivo da conversa: levar o cliente a {GOALS[goal]}." + (f" {setup.goal_detail.strip()}" if setup.goal_detail.strip() else ""))
    discover = setup.discover or niche.get("discover") or []
    if discover:
        lines.append("O que descobrir aos poucos, sem questionário: " + "; ".join(item.strip() for item in discover) + ".")
    handoff = setup.handoff.strip() or niche.get("handoff", "")
    if handoff:
        lines.append(f"Passe para uma pessoa da equipe (handoff) quando: {handoff}")
    if setup.tone:
        lines.append("Tom: " + ("formal e cordial, tratando por senhor ou senhora quando fizer sentido." if setup.tone == "formal"
                                 else "descontraído e próximo, como uma conversa entre conhecidos."))
    lines.append("Emojis: no máximo um, quando combinar." if setup.emojis else "Não use emojis.")
    if setup.never_say.strip():
        lines.append(f"Nunca diga ou prometa: {setup.never_say.strip()}")
    if niche.get("care"):
        lines.append(f"Cuidados deste mercado: {niche['care']}")
    if setup.extra.strip():
        lines.append(f"Outras informações: {setup.extra.strip()}")
    return "\n".join(lines)


async def read_setup(connection, organization_uuid) -> ServiceSetup:
    """The workspace's setup; an empty one before migration 0038 (a savepoint keeps the caller's transaction)."""
    try:
        async with connection.transaction():
            row = await (await connection.execute(
                "SELECT service FROM sales_profiles WHERE organization_id=%s", (organization_uuid,))).fetchone()
    except Exception:  # noqa: BLE001 - column not there yet: the prompts work as before
        return ServiceSetup()
    return stored_setup(row["service"] if row else None)


class ServiceSetupRepository:
    def __init__(self, postgres: PostgresRepository) -> None:
        self._postgres = postgres

    async def get(self, organization_id: str) -> dict[str, Any]:
        async with self._postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                "SELECT service,updated_at FROM sales_profiles WHERE organization_id=%s",
                (_uuid("organization", organization_id),))).fetchone()
        setup = stored_setup(row["service"] if row else None)
        return {"setup": setup.model_dump(), "configured": is_configured(setup), "updated_at": _iso(row["updated_at"]) if row else None}

    async def save(self, organization_id: str, setup: ServiceSetup) -> dict[str, Any]:
        data = setup.model_dump()
        data["services"] = [{"name": item["name"].strip(), "price": item["price"].strip()} for item in data["services"] if item["name"].strip()]
        data["discover"] = [item.strip() for item in data["discover"] if item.strip()]
        async with self._postgres._transaction(organization_id) as connection:
            await connection.execute(
                """INSERT INTO sales_profiles(organization_id,service) VALUES(%s,%s)
                   ON CONFLICT (organization_id) DO UPDATE SET service=excluded.service,updated_at=now()""",
                (_uuid("organization", organization_id), Jsonb(data)))
        return await self.get(organization_id)


def niche_catalog() -> list[dict[str, Any]]:
    return [{"id": key, "label": value["label"], "goal": value["goal"], "discover": value["discover"], "handoff": value["handoff"],
             "care": value["care"], "examples": value["examples"], "payment_label": value["payment_label"]} for key, value in NICHES.items()]


def create_service_setup_router(repository: ServiceSetupRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/sales", tags=["sales"])

    @router.get("/service")
    async def get_setup(context: Annotated[RequestContext, Depends(authenticated_context)]) -> dict[str, Any]:
        return {**await repository.get(context.organization_id), "niches": niche_catalog(), "goals": GOALS}

    @router.put("/service")
    async def save_setup(setup: ServiceSetup, context: Annotated[RequestContext, Depends(authenticated_context)]) -> dict[str, Any]:
        if context.role not in {"owner", "admin", "operator"}:
            raise ApiError(403, "insufficient_role", "Acesso restrito a quem administra o atendimento.")
        if setup.niche and setup.niche != "outro" and setup.niche not in NICHES:
            raise ApiError(422, "unknown_niche", "Escolha um nicho da lista ou use Outro.")
        return {**await repository.save(context.organization_id, setup), "niches": niche_catalog(), "goals": GOALS}

    return router
