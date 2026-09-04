from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.core.intents import IntentRouter


def test_routes_correction_inbox_location() -> None:
    router = IntentRouter()

    assert router.route("onde estão as correções?").name == "correction_inbox"
    assert router.route("mostre o arquivo de correções").name == "correction_inbox"
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


def test_routes_feminine_article_without_including_it_in_application_name():
    intent = IntentRouter().route("Kiara, abra a calculadora.")
    assert intent.name == "open_application"
    assert intent.parameters == {"application": "calculadora"}


def test_routes_powershell_acceptance_phrase():
    intent = IntentRouter().route("Kiara, execute no PowerShell o comando hostname.")
    assert intent.name == "powershell"
    assert intent.parameters == {"command": "hostname"}


def test_routes_compound_cmd_ping_without_treating_it_as_app_name():
    intent = IntentRouter().route("abra o cmd e de um ping -a em 8.8.8.8")

    assert intent.name == "network_ping"
    assert intent.parameters == {"resolve_name": "-a", "target": "8.8.8.8"}


def test_routes_url():
    assert IntentRouter().route("abra https://example.com").name == "open_url"


def test_routes_colloquial_open_command() -> None:
    intent = IntentRouter().route("abre o Discord")

    assert intent.name == "open_application"
    assert intent.parameters == {"application": "Discord"}


def test_routes_web_search_before_generic_application() -> None:
    intent = IntentRouter().route("abra o google e pesquise por diagnóstico de rede")
    assert intent.name == "web_search"
    assert intent.parameters == {"query": "diagnóstico de rede"}


def test_routes_natural_search_subject_with_google_at_end() -> None:
    router = IntentRouter()
    intent = router.route("pesquise sobre o internacional no google")
    assert intent.name == "web_search"
    assert intent.parameters == {"query": "o internacional"}
    assert router.route("busque no Google sobre clima em Porto Alegre").parameters == {
        "query": "clima em Porto Alegre"
    }
    assert router.route("abra o clima tempo no google").parameters == {"query": "clima tempo"}
    assert router.route("abra o windy no google").parameters == {"query": "windy"}


def test_routes_calendar_and_teams_requests_without_model_fallback() -> None:
    router = IntentRouter()

    local = router.route("veja meu calendário da semana")
    teams = router.route("veja minhas reuniões do teams essa semana")

    assert local.name == "work_calendar"
    assert local.parameters == {"period": "semana"}
    assert teams.name == "work_calendar"
    assert teams.parameters == {"period": "semana"}


def test_routes_current_sports_and_betting_to_realtime_research() -> None:
    router = IntentRouter()

    assert router.route("qual a escalação do inter hoje?").name == "realtime_research"
    assert (
        router.route("melhores palpites de aposta para os jogos de hoje").name
        == "realtime_research"
    )


def test_routes_multi_lead_prospecting_before_simple_web_search() -> None:
    messages = (
        (
            "kiara, busque num raio de 50km de onde estamos, no google, 25 profissionais "
            "dentistas, que voce identifique que eles não possuem sites próprios, para que "
            "possamos chama-los no whats e oferecer nossos serviços de criação de site"
        ),
        "kiara, busque 25 profissionais dentistas que não possuem site",
        (
            "kiara, me traga no minimo 50 dentistas que não possuam sites, pesquise em "
            "todo o Rio Grande do Sul"
        ),
        (
            "busque 50 dentistas sem site em todo o Rio Grande do Sul e me traga os "
            "numeros de whatssap"
        ),
    )

    assert all(
        IntentRouter().route(message).name == "local_lead_research" for message in messages
    )


def test_understands_colloquial_prospecting_and_small_typos() -> None:
    router = IntentRouter()
    messages = (
        "acha uns dentissta sem pagina propria e pega o zap deles",
        "preciso de uma lista de odontologistas sem presença digital com contato",
        "procure clínicas que não tenham domínio e traga o telefone",
        "quero prospectar dentistas pelo whats que ainda não têm site",
    )

    assert all(router.route(message).name == "local_lead_research" for message in messages)


def test_concept_matcher_does_not_capture_unrelated_searches() -> None:
    router = IntentRouter()

    assert router.route("busque no Google como criar um site").name == "web_search"
    assert router.route("procure o telefone da prefeitura").name == "web_search"
    assert router.route("quero marcar uma consulta com dentista").name == "conversation"


def test_routes_generic_web_navigation_and_page_actions() -> None:
    router = IntentRouter()
    domain = router.route("abra example.com")
    assert domain.name == "open_website"
    assert domain.parameters == {"target": "example.com"}
    site = router.route("abra o site da prefeitura de Curitiba")
    assert site.name == "open_website"
    assert site.parameters == {"target": "prefeitura de Curitiba"}
    fill = router.route("digite no campo Pesquisa com teclado mecânico")
    assert fill.name == "browser_fill"
    assert fill.parameters == {"label": "Pesquisa", "text": "teclado mecânico"}
    click = router.route("clique no botão Buscar")
    assert click.name == "browser_click"
    assert click.parameters == {"role": "botão", "name": "Buscar"}
    assert router.route("leia esta página").name == "browser_read"


def test_routes_social_message_with_explicit_recipient_and_text() -> None:
    intent = IntentRouter().route(
        "mande uma mensagem no whatsapp para +5511999999999 dizendo chego às 18h"
    )
    assert intent.name == "social_message"
    assert intent.parameters == {
        "platform": "whatsapp",
        "recipient": "+5511999999999",
        "text": "chego às 18h",
    }


def test_routes_instagram_direct_message_variant() -> None:
    intent = IntentRouter().route(
        "abra o direct de @maria no instagram e escreva olá, tudo bem? e envie"
    )
    assert intent.name == "social_message_direct"
    assert intent.parameters["platform"] == "instagram"
    assert intent.parameters["recipient"] == "@maria"
    assert intent.parameters["text"] == "olá, tudo bem?"


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


def test_routes_helpdesk_diagnostic_and_verification() -> None:
    router = IntentRouter()
    diagnostic = router.route("faça um diagnóstico dos drivers")
    assert diagnostic.name == "helpdesk_diagnostic"
    assert diagnostic.parameters["category"] in {"driver", "drivers"}
    assert router.route("faça um diagnóstico do computador").name == "helpdesk_diagnostic"
    assert router.route("verifique se resolveu").name == "helpdesk_verify"


def test_routes_current_date_and_time_without_model_guessing() -> None:
    router = IntentRouter()
    assert router.route("que dia é hoje?").name == "current_datetime"
    assert router.route("qual é a data de hoje?").name == "current_datetime"
    assert router.route("que horas são?").name == "current_datetime"


def test_routes_screen_monitoring_phrases_to_on_demand_screen_context() -> None:
    router = IntentRouter()
    assert router.route("acompanhe o que estou fazendo na tela").name == "screen_context"
    assert router.route("observe minha tela e me oriente").name == "screen_context"


def test_routes_recurring_automation_before_embedded_url() -> None:
    intent = IntentRouter().route(
        "crie uma automação para abrir https://example.com a cada 2 horas"
    )
    assert intent.name == "create_recurring_automation"
    assert intent.parameters == {
        "url": "https://example.com",
        "interval": "2",
        "unit": "horas",
    }
    assert IntentRouter().route("liste minhas automações").name == "list_automations"


def test_routes_explicit_recovery_plan_resume() -> None:
    intent = IntentRouter().route("execute o plano de recuperação 42")
    assert intent.name == "resume_goal"
    assert intent.parameters == {"goal_id": "42"}


def test_routes_business_site_creation_with_reference_image() -> None:
    intent = IntentRouter().route(
        "crie um site completo para Café Aurora, cafeteria artesanal usando a imagem cafe.png"
    )
    assert intent.name == "build_business_site"
    assert intent.parameters == {
        "business_info": "Café Aurora, cafeteria artesanal",
    }


def test_routes_mcp_discovery_and_explicit_json_call() -> None:
    router = IntentRouter()
    assert router.route("liste os servidores MCP").name == "list_mcp_servers"
    discovery = router.route("liste as ferramentas MCP do servidor arquivos")
    assert discovery.name == "discover_mcp_tools"
    assert discovery.parameters == {"server": "arquivos"}
    call = router.route(
        'execute a ferramenta MCP buscar do servidor arquivos com argumentos {"q":"teste"}'
    )
    assert call.name == "call_mcp_tool"
    assert call.parameters["tool"] == "buscar"
    assert call.parameters["server"] == "arquivos"


def test_routes_personal_center_commands() -> None:
    router = IntentRouter()
    assert router.route("liste minhas tarefas").name == "list_personal_tasks"
    task = router.route("adicione uma tarefa comprar leite")
    assert task.name == "add_personal_task"
    assert task.parameters == {"title": "comprar leite"}
    event = router.route("agende consulta para amanhã às 14:30")
    assert event.name == "add_personal_event"
    assert event.parameters["hour"] == "14"
    assert event.parameters["minute"] == "30"
    assert router.route("liste meus compromissos").name == "list_personal_events"
    assert router.route("encontre o arquivo contrato").name == "search_personal_files"


def test_routes_email_draft_without_sending() -> None:
    intent = IntentRouter().route(
        "crie um rascunho de email para pessoa@example.com assunto Olá mensagem Tudo bem?"
    )
    assert intent.name == "draft_email"
    assert intent.parameters == {
        "to": "pessoa@example.com",
        "subject": "Olá",
        "body": "Tudo bem?",
    }


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
