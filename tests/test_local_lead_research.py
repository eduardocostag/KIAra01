from __future__ import annotations

import json

import pytest

from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.leads import LeadStore
from app.models import ScreenContext, ToolResult


class LeadTools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, name: str, **parameters: object) -> ToolResult:
        self.calls.append((name, parameters))
        text = "Dentista Exemplo telefone 51999999999 Instagram " * 8
        return ToolResult(True, output="Google", metadata={"text": text})


class MapsLeadTools(LeadTools):
    def names(self) -> tuple[str, ...]:
        return ("google_maps_business_search",)

    async def execute(self, name: str, **parameters: object) -> ToolResult:
        self.calls.append((name, parameters))
        return ToolResult(
            True,
            output="3 fichas lidas",
            metadata={
                "businesses": [
                    {
                        "name": "Dra. Sem Site",
                        "address": "Centro, Canoas",
                        "phone": "(51) 99999-1111",
                        "whatsapp": "(51) 99999-1111",
                        "website": "",
                        "maps_url": "https://www.google.com/maps/place/sem-site",
                    },
                    {
                        "name": "Dr. Com Site",
                        "whatsapp": "(51) 99999-2222",
                        "website": "https://dentista.example",
                    },
                    {
                        "name": "Clínica Sem WhatsApp",
                        "whatsapp": "",
                        "website": "",
                    },
                ]
            },
        )


class BlockedLeadTools(LeadTools):
    async def execute(self, name: str, **parameters: object) -> ToolResult:
        self.calls.append((name, parameters))
        return ToolResult(False, error="fonte bloqueada")


class LeadLLM:
    def __init__(self) -> None:
        self.prompts: list[dict] = []

    async def generate(self, prompt: str) -> str:
        parsed = json.loads(prompt)
        self.prompts.append(parsed)
        if parsed["role"] == "extrator_de_candidatos_de_prospeccao":
            return json.dumps(
                {
                    "candidates": [
                        {
                            "name": "Dentista Exemplo",
                            "location": "Canoas, RS",
                            "whatsapp": "(51) 99999-9999",
                            "source": "Google",
                        }
                    ]
                }
            )
        return "1 lead validado; ausência de site é apenas triagem."


def make_core(tools: LeadTools, llm: LeadLLM) -> AgentCore:
    return AgentCore(tools, llm, ContextManager(lambda: ScreenContext()))


@pytest.mark.asyncio
async def test_lead_research_requests_a_real_radius_center() -> None:
    tools, llm = LeadTools(), LeadLLM()
    core = make_core(tools, llm)

    response = await core.handle(
        "busque 25 dentistas sem site num raio de 50km de onde estamos para chamar no WhatsApp"
    )

    assert "cidade e o estado" in response
    assert tools.calls == []


@pytest.mark.asyncio
async def test_lead_research_without_any_location_requests_one() -> None:
    tools, llm = LeadTools(), LeadLLM()

    response = await make_core(tools, llm).handle(
        "kiara, busque 25 profissionais dentistas que não possuem site"
    )

    assert "cidade e o estado" in response
    assert tools.calls == []
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_lead_research_resumes_after_location_and_requires_grounded_output() -> None:
    tools, llm = LeadTools(), LeadLLM()
    core = make_core(tools, llm)
    await core.handle(
        "busque 25 dentistas sem site num raio de 50km de onde estamos para chamar no WhatsApp"
    )

    response = await core.handle("Canoas, RS")

    assert response.startswith("1 lead validado")
    assert len(tools.calls) == 4
    assert all(name == "browser_navigate" for name, _ in tools.calls)
    assert len(llm.prompts) == 2
    assert llm.prompts[1]["requested_count"] == 25
    assert "SOMENTE" in llm.prompts[1]["instructions"]
    assert "exclua o candidato" in llm.prompts[1]["instructions"]
    assert "nenhum site próprio encontrado" in llm.prompts[1]["instructions"]


@pytest.mark.asyncio
async def test_blocked_lead_research_never_opens_visible_browser() -> None:
    tools, llm = BlockedLeadTools(), LeadLLM()

    response = await make_core(tools, llm).handle(
        "busque dentistas sem site em Canoas, RS com WhatsApp confirmado"
    )

    assert tools.calls
    assert all(name == "browser_navigate" for name, _parameters in tools.calls)
    assert "segundo plano" in response
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_lead_research_accepts_city_name_as_follow_up_location() -> None:
    tools, llm = MapsLeadTools(), LeadLLM()
    core = make_core(tools, llm)
    await core.handle(
        "busque 25 dentistas sem site num raio de 50km de onde estamos para chamar no WhatsApp"
    )

    response = await core.handle("Porto Alegre")

    assert "Dra. Sem Site" in response
    assert "cidade e o estado" not in response
    assert tools.calls == [
        (
            "google_maps_business_search",
            {"query": "dentistas em Porto Alegre, RS", "limit": 50},
        )
    ]


@pytest.mark.asyncio
async def test_lead_research_supports_any_business_niche_not_only_dentists() -> None:
    tools, llm = MapsLeadTools(), LeadLLM()

    response = await make_core(tools, llm).handle(
        "Kiara, busque 25 clínicas de estética em Porto Alegre, RS. "
        "Traga somente profissionais com WhatsApp confirmado e nenhum site próprio."
    )

    assert "Dra. Sem Site" in response
    assert tools.calls == [
        (
            "google_maps_business_search",
            {"query": "clínicas de estética em Porto Alegre, RS", "limit": 50},
        )
    ]


@pytest.mark.asyncio
async def test_maps_flow_returns_only_confirmed_whatsapp_without_website() -> None:
    tools, llm = MapsLeadTools(), LeadLLM()

    response = await make_core(tools, llm).handle(
        "Kiara, busque no Google 25 dentistas em Canoas, RS, num raio de 50 km. "
        "Traga somente profissionais com WhatsApp confirmado e nenhum site próprio."
    )

    assert "Dra. Sem Site" in response
    assert "Dr. Com Site" not in response
    assert "Clínica Sem WhatsApp" not in response
    assert tools.calls == [
        (
            "google_maps_business_search",
            {"query": "dentistas em Canoas, RS", "limit": 50},
        )
    ]
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_maps_flow_persists_sales_ready_artifacts_without_false_sql(tmp_path) -> None:
    tools, llm = MapsLeadTools(), LeadLLM()
    store = LeadStore(tmp_path / "leads.db")
    core = AgentCore(tools, llm, ContextManager(lambda: ScreenContext()), lead_store=store)

    response = await core.handle(
        "busque dentistas sem site em Canoas, RS com WhatsApp confirmado"
    )

    lead = store.list()[0]
    assert "em qualificação comercial" in response
    assert lead.qualification_data["status"] != "sql_pronto"
    assert {"timing", "autoridade", "capacidade"} <= set(
        lead.qualification_data["missing_information"]
    )
    assert lead.dossier_data["verified_facts"] == []
    assert store.observations(lead.id)
    assert lead.dossier_data["discovery_questions"]
    assert lead.sales_artifacts["opening_message"]
    assert lead.sales_artifacts["approval_required"] is True
    assert lead.sales_artifacts["proposal"]["approval_gates"]
    store.close()


@pytest.mark.asyncio
async def test_statewide_rs_request_uses_maps_batches_without_ai_provider() -> None:
    tools, llm = MapsLeadTools(), LeadLLM()

    response = await make_core(tools, llm).handle(
        "kiara, busque em todas as cidades do Rio Grande do Sul, por dentistas que não "
        "possuem site e me traga a lista completa com nome, cidade e numero de whatsapp"
    )

    assert "polos municipais do RS" in response
    assert len(tools.calls) == 20
    assert all(name == "google_maps_business_search" for name, _ in tools.calls)
    assert llm.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        "kiara, me traga no minimo 50 dentistas que não possuam sites, pesquise em todo o Rio Grande do Sul",
        "busque 50 dentistas sem site em todo o Rio Grande do Sul e me traga os numeros de whatssap",
    ],
)
async def test_statewide_variants_never_fall_back_to_ai(message: str) -> None:
    tools, llm = MapsLeadTools(), LeadLLM()

    response = await make_core(tools, llm).handle(message)

    assert "polos municipais do RS" in response
    assert tools.calls
    assert llm.prompts == []
