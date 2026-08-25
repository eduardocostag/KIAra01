from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.core.intents import IntentRouter
from app.models import ScreenContext


class _DummyTools:
    async def execute(self, name, **kwargs):
        raise AssertionError(f"não deveria executar ferramenta: {name}")


class _DummyLLM:
    capabilities = frozenset({"generate"})


def test_routes_application_without_hardcoding_notepad():
    intent = IntentRouter().route("Kiara, abra o bloco de notas.")
    assert intent.name == "open_application"
    assert intent.parameters == {"application": "bloco de notas"}


def test_routes_powershell_acceptance_phrase():
    intent = IntentRouter().route("Kiara, execute no PowerShell o comando hostname.")
    assert intent.name == "powershell"
    assert intent.parameters == {"command": "hostname"}


def test_routes_url():
    assert IntentRouter().route("abra https://example.com").name == "open_url"


def test_routes_obsidian_commands_before_generic_open_application():
    router = IntentRouter()
    assert router.route("sincronize o Obsidian").name == "sync_obsidian"
    search = router.route("pesquise no Obsidian por configuração de rede")
    assert search.name == "search_obsidian"
    assert search.parameters["query"] == "configuração de rede"
    assert router.route("abra a nota Início no Obsidian").name == "open_obsidian_note"
    assert router.route("salve no Obsidian: teste importante").name == "save_obsidian_note"


def test_routes_screen_capability_without_triggering_capture():
    assert IntentRouter().route("consegue ver minha tela?").name == "screen_capability"


def test_routes_common_screen_description_variants():
    router = IntentRouter()
    assert router.route("oque esta vendo?").name == "screen_context"
    assert router.route("o que você vê na tela?").name == "screen_context"
    assert router.route("descreva minha tela").name == "screen_context"
    assert router.route("olha minha tela").name == "screen_context"
    assert router.route("olhe a tela e me explica").name == "screen_context"
    assert router.route("analise o que está na tela").name == "screen_context"


def test_desktop_assistant_response_has_summary_observation_risk_and_next_steps():
    core = AgentCore(
        _DummyTools(),
        _DummyLLM(),
        ContextManager(
            lambda: ScreenContext(
                active_application="Google Chrome",
                window_title="Dashboard de vendas",
            )
        ),
    )
    response = core._format_desktop_assistant_response(
        "olha minha tela",
        ScreenContext(active_application="Google Chrome", window_title="Dashboard de vendas"),
        "A tela mostra métricas de faturamento, filtros e gráfico de desempenho.",
    )
    assert "Resumo" in response
    assert "Observação" in response
    assert "Risco" in response
    assert "Próximos passos" in response


def test_thinking_text_cycles_with_three_dots():
    from app.ui.desktop import thinking_text

    assert thinking_text(0) == "Pensando."
    assert thinking_text(1) == "Pensando.."
    assert thinking_text(2) == "Pensando..."
    assert thinking_text(3) == "Pensando."
