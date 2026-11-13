import json
from pathlib import Path

import pytest
import yaml

from app.bootstrap import build_app
from app.config import Settings
from app.integrations.operational_skills import OperationalSkills
from app.tools.web_studio import LandingPageTemplatesTool
from app.web_studio.generator import BusinessSiteGenerator
from app.web_studio.landing_system import (
    SKILL_ROOT,
    SOURCE_ROOT,
    build_template_preview,
    generation_guidance,
    template_catalog,
)


def test_skill_is_discoverable_with_complete_inventory_and_references():
    skills = OperationalSkills()
    assert skills.relevant("crie um site com landing page cinematografica")[0]["name"] == "kiara-web-studio"
    catalog = json.loads(skills.read("kiara-web-studio", "references/catalog.json"))
    assert len(catalog["templates"]) == len(template_catalog()) == 33
    assert len(catalog["skills"]) == 9
    assert len(catalog["repositories"]) == 5
    assert catalog["status"] == "reference_only"
    brief = yaml.safe_load(skills.read("kiara-web-studio", "assets/landing-page-system/templates/brief.yaml"))
    assert "offer" in brief["business"]
    for entry in catalog["skills"]:
        assert (SKILL_ROOT / entry["entrypoint"]).is_file()


def test_generation_receives_real_catalog_and_preserves_isolation():
    prompt = json.loads(BusinessSiteGenerator._project_prompt("Cliente", "Informacoes reais", "Referencia"))
    assert len(prompt["landing_page_system"]["templates"]) == 33
    policy = json.loads((SOURCE_ROOT / "config/publishing-policy.json").read_text(encoding="utf-8"))
    assert generation_guidance()["budgets"]["image_bytes"] == policy["assetBudgets"]["imageBytes"]
    assert any("no external" in rule.lower() for rule in prompt["requirements"])


@pytest.mark.parametrize("template", ["dentista-template-1", "psicologo-template-1", "educador-fisico-template-1"])
def test_preview_is_isolated_has_shared_assets_and_is_not_claimed_personalized(tmp_path, template):
    original = (SOURCE_ROOT / "templates" / template / "index.html").read_bytes()
    target = build_template_preview(template, tmp_path)
    assert target.is_relative_to(tmp_path)
    assert (target / "shared/system").is_dir()
    text = (target / "index.html").read_text(encoding="utf-8")
    assert 'content="noindex, nofollow, noarchive"' in text
    assert "../system/" not in text
    assert "demonstrativo" in text
    assert (SOURCE_ROOT / "templates" / template / "index.html").read_bytes() == original
    report = json.loads((target / "kiara-preview.json").read_text(encoding="utf-8"))
    assert not report["published"] and not report["personalized"] and not report["quality_verified"]
    assert build_template_preview(template, tmp_path) != target


@pytest.mark.parametrize("template", ["../../other", "..", "C:/Windows", "missing", "dentista-template-1/../../other"])
def test_template_argument_cannot_escape_or_overwrite_output(tmp_path, template):
    marker = tmp_path / "preserve.txt"
    marker.write_text("keep")
    with pytest.raises(ValueError):
        build_template_preview(template, tmp_path)
    assert marker.read_text() == "keep"
    assert list(tmp_path.iterdir()) == [marker]


@pytest.mark.asyncio
async def test_template_tool_returns_truthful_preview_metadata(tmp_path):
    tool = LandingPageTemplatesTool(tmp_path)
    result = await tool.execute(action="list")
    assert len(result.metadata["templates"]) == 33
    preview = await tool.execute(action="preview", template="beleza-template-1")
    assert preview.success
    assert preview.metadata["published"] is False
    assert preview.metadata["quality_verified"] is False
    assert Path(preview.metadata["project_path"]).is_dir()


@pytest.mark.asyncio
async def test_runtime_registers_template_tool_without_requiring_a_vision_call(tmp_path, monkeypatch):
    monkeypatch.setenv("KIARA_LLM_PROVIDER", "local")
    core, _ = build_app(Settings(root=tmp_path, raw={
        "personal": {"enabled": False}, "knowledge": {"enabled": False},
        "memory": {"enabled": False}, "web_studio": {"enabled": True},
        "video_studio": {"enabled": False},
    }))
    try:
        assert "landing_page_templates" in core.tools.names()
    finally:
        await core.aclose()
