from __future__ import annotations

from app.consumers import ConsumerStore, OrganicIntentClassifier
from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.core.intents import IntentRouter
from app.models import ScreenContext, ToolResult


class OrganicTools:
    def __init__(self, results: list[dict[str, str]]) -> None:
        self.results = results
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, name: str, **parameters: object) -> ToolResult:
        self.calls.append((name, parameters))
        return ToolResult(True, output="busca concluída", metadata={"results": self.results})


class NoLLM:
    async def generate(self, _prompt: str) -> str:
        raise AssertionError("Descoberta orgânica não deve inventar resultados com LLM.")


def test_routes_explicit_organic_b2c_research_before_business_research() -> None:
    intent = IntentRouter().route(
        "busque 12 consumidores B2C orgânicos para estética no Rio Grande do Sul"
    )

    assert intent.name == "organic_consumer_research"
    assert intent.parameters["limit"] == 12
    assert intent.parameters["query"] == "estetica"
    assert intent.parameters["location"] == "rio grande do sul"


def test_classifier_accepts_purchase_intent_but_rejects_likes_and_non_social_urls() -> None:
    classifier = OrganicIntentClassifier()

    opportunity = classifier.classify(
        url="https://www.instagram.com/p/abc/",
        title="Procuro clínica de estética",
        excerpt="Preciso de indicação em Porto Alegre esta semana",
        location="Rio Grande do Sul",
    )

    assert opportunity is not None
    assert opportunity.platform == "instagram"
    assert opportunity.intent_score >= 70
    assert classifier.classify(
        url="https://www.instagram.com/p/like/", title="Curti esta foto", excerpt=""
    ) is None
    assert classifier.classify(
        url="https://example.com/post", title="Preciso de estética", excerpt=""
    ) is None


async def test_organic_research_saves_reviewable_signal_without_creating_person(tmp_path) -> None:
    store = ConsumerStore(tmp_path / "consumers.db")
    tools = OrganicTools([
        {
            "url": "https://www.instagram.com/p/abc/",
            "title": "Procuro clínica de estética",
            "excerpt": "Preciso de indicação em Porto Alegre e quero saber o valor",
            "platform": "instagram",
        },
        {
            "url": "https://example.com/nope",
            "title": "Procuro clínica",
            "excerpt": "",
            "platform": "web",
        },
    ])
    core = AgentCore(
        tools, NoLLM(), ContextManager(lambda: ScreenContext()), consumer_store=store
    )

    response = await core.handle(
        "busque 10 consumidores B2C orgânicos para estética no Rio Grande do Sul"
    )

    assert tools.calls == [(
        "organic_consumer_search",
        {"query": "estetica", "location": "rio grande do sul", "limit": 10},
    )]
    assert "1 oportunidade" in response
    assert "sem autorização" in response
    assert store.list_people() == []
    opportunities = store.list_organic_opportunities()
    assert len(opportunities) == 1
    assert opportunities[0]["status"] == "revisar"

    # A mesma URL é atualizada, nunca duplicada.
    await core.handle("busque 10 consumidores B2C orgânicos para estética no Rio Grande do Sul")
    assert len(store.list_organic_opportunities()) == 1
    store.close()
