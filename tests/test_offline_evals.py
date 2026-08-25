from app.agents.router import AgentRouter
from app.evals import ContractCase, OfflineEvaluator, RoutingCase
from app.providers.llm import LocalFallbackProvider


def test_routing_eval_is_offline_and_reports_accuracy_f1_and_latency():
    evaluator = OfflineEvaluator()
    router = AgentRouter(LocalFallbackProvider())
    result = evaluator.evaluate_routing(
        router,
        (
            RoutingCase("software", "Ajude a depurar este bug em Python", frozenset({"engenharia_de_software"})),
            RoutingCase("helpdesk", "Minha impressora está com erro", frozenset({"helpdesk"})),
            RoutingCase("general", "Conte uma história curta", frozenset({"generalista"})),
        ),
    )
    assert result.total == 3
    assert result.accuracy == 1.0
    assert result.macro_f1 == 1.0
    assert result.latency_p50_ms >= 0
    assert not result.failures


def test_contract_eval_normalizes_accents_and_explains_failures():
    evaluator = OfflineEvaluator()
    result = evaluator.evaluate_contracts(
        (
            ContractCase(
                "safe-hardware",
                "É uma hipótese. Antes de atualizar a BIOS, confirme o backup.",
                required_all=("hipotese", "confirme"),
                forbidden=("já executei",),
            ),
            ContractCase("false-action", "Já executei o reparo.", forbidden=("já executei",)),
        )
    )
    assert result.total == 2
    assert result.passed == 1
    assert result.failures[0].startswith("false-action:")


def test_report_can_be_serialized(tmp_path):
    evaluator = OfflineEvaluator()
    report = evaluator.evaluate_contracts((ContractCase("ok", "resposta útil"),))
    assert report.pass_rate == 1.0
