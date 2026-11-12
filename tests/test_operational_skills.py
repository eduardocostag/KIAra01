from pathlib import Path

import pytest

from app.bootstrap import build_app
from app.config import Settings
from app.core.context import ContextManager
from app.integrations.operational_skills import OperationalSkills
from app.models import ScreenContext
from app.tools.operational_skills import OperationalSkillTool


@pytest.mark.asyncio
async def test_bootstrap_falls_back_when_optional_maps_binary_is_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("KIARA_MAPS_SCRAPER_EXECUTABLE", raising=False)
    monkeypatch.setenv("KIARA_LLM_PROVIDER", "local")
    core, _ = build_app(Settings(root=tmp_path, raw={
        "integrations": {"maps_scraper": {"enabled": True}},
        "personal": {"enabled": False}, "knowledge": {"enabled": False},
        "memory": {"enabled": False}, "web_studio": {"enabled": False},
    }))
    try:
        assert {"operational_skill", "instagram_content_check", "google_maps_business_search"} <= (
            set(core.tools.names())
        )
        assert core.tools._tools["google_maps_business_search"].__class__.__name__ == (
            "GoogleMapsBusinessSearchTool"
        )
    finally:
        await core.aclose()


def test_packaged_instagram_skills_and_references():
    skills = OperationalSkills()
    names = {item["name"] for item in skills.catalog()}
    assert {"ig-caption", "ig-reel", "ig-human", "ig-dm"} <= names
    assert '"' in skills.read("ig-reel", "hooks.json")


@pytest.mark.parametrize(("query", "expected"), [
    ("crie um roteiro de reel para Instagram", "ig-reel"),
    ("analise um gancho de reel no Instagram", "ig-reel"),
    ("escreva legenda para Instagram", "ig-caption"),
    ("crie um carrossel para Instagram", "ig-carousel"),
    ("prospectar dentistas em Curitiba", "google-maps-scraper"),
    ("captar empresas nos mapas", "google-maps-scraper"),
    ("prospecção de clínicas", "google-maps-scraper"),
    ("captação de empresas", "google-maps-scraper"),
    ("configurar freellmapi para responder", "kiara-freellmapi"),
])
def test_portuguese_skill_routing(query, expected):
    assert OperationalSkills().relevant(query)[0]["name"] == expected


@pytest.mark.parametrize("resource", ["../../../../config/kiara.yaml", "../ig-human/SKILL.md",
                                      "hookscore.py", "missing.json"])
def test_skill_read_is_confined(resource):
    with pytest.raises(ValueError):
        OperationalSkills().read("ig-reel", resource)


def test_context_loads_relevant_reference_without_executing(tmp_path: Path):
    folder = tmp_path / "operational_skills" / "kiara-test"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        "---\nname: kiara-test\ndescription: Instagram legenda\n---\nUse ferramentas locais.",
        encoding="utf-8",
    )
    context = ContextManager(lambda: ScreenContext(),
                             operational_skills=OperationalSkills(tmp_path))
    result = context.assemble("Instagram legenda")
    assert result["operational_skills"][0]["trust"] == "untrusted_reference"
    assert "Use ferramentas locais" in result["operational_skills"][0]["content"]
    assert context.assemble("hostname")["operational_skills"] == []


@pytest.mark.asyncio
async def test_skill_tool_lists_and_reads():
    tool = OperationalSkillTool(OperationalSkills())
    result = await tool.execute("list")
    assert len(result.metadata["skills"]) >= 13
    assert (await tool.execute("read", "ig-caption")).success
    with pytest.raises(ValueError):
        await tool.execute("read", "not-installed")
