from __future__ import annotations

import json

from app.helpdesk import SystemDiagnosticsTool, compare_snapshots
from app.models import PermissionLevel
from app.perception.analysis import parse_screen_analysis


async def test_diagnostics_tool_is_fixed_read_only_and_structured() -> None:
    observed: list[tuple[str, float]] = []

    def runner(script: str, timeout: float) -> str:
        observed.append((script, timeout))
        return json.dumps({"problem_count": 1, "devices": [{"error_code": 10}]})

    tool = SystemDiagnosticsTool(runner=runner, timeout_seconds=4)
    tool.validate({"category": "drivers"})
    result = await tool.execute(category="drivers")

    assert tool.permission_level == PermissionLevel.READ_ONLY
    assert result.success is True
    assert result.metadata["verified"] is True
    assert result.metadata["snapshot"]["problem_count"] == 1
    assert "Win32_PnPEntity" in observed[0][0]
    assert observed[0][1] == 4


async def test_diagnostics_rejects_unknown_or_extra_parameters() -> None:
    tool = SystemDiagnosticsTool(runner=lambda *_: "{}")
    for parameters in ({"category": "processes"}, {"category": "overview", "command": "x"}):
        try:
            tool.validate(parameters)
        except ValueError:
            pass
        else:  # pragma: no cover - assertion branch
            raise AssertionError("invalid diagnostic parameters were accepted")


def test_snapshot_comparison_requires_category_specific_success_criterion() -> None:
    comparison = compare_snapshots(
        {"problem_count": 1},
        {"problem_count": 0},
        category="drivers",
    )
    assert comparison["changed"] is True
    assert comparison["resolution_confirmed"] is True
    assert comparison["changes"] == [
        {"field": "problem_count", "before": 1, "after": 0}
    ]
    generic = compare_snapshots({"value": 1}, {"value": 0}, category="overview")
    assert generic["resolution_confirmed"] is False


def test_visual_analysis_accepts_bounded_json_and_degrades_honestly() -> None:
    analysis = parse_screen_analysis(
        json.dumps(
            {
                "application": "Editor",
                "subject": "Falha de importação",
                "state": "execução interrompida",
                "visible_errors": ["ModuleNotFoundError"],
                "evidence": ["traceback visível"],
                "hypotheses": ["dependência ausente"],
                "suggested_checks": ["confirmar ambiente virtual"],
                "uncertainty": "pacote esperado não está visível",
            }
        )
    )
    assert analysis.visible_errors == ("ModuleNotFoundError",)
    assert analysis.as_context()["hypotheses"] == ["dependência ausente"]

    fallback = parse_screen_analysis("descrição livre", application="Editor")
    assert fallback.state == "não estruturado"
    assert "JSON válido" in fallback.uncertainty
