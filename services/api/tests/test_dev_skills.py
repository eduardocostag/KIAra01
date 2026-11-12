"""Tests for engineering skills catalog and loader under kiara_api.platform.skills."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.platform.skills import get_platform_skills, load_skill_metadata, SKILLS_DIR

EXPECTED_SKILLS = {
    "tdd",
    "codebase-design",
    "code-review",
    "diagnosing-bugs",
    "writing-docs",
    "pr-guidelines",
}


def test_skills_directory_exists_and_contains_skills():
    assert SKILLS_DIR.is_dir()
    skills = get_platform_skills()
    skill_names = {s["name"] for s in skills}
    assert EXPECTED_SKILLS.issubset(skill_names)


@pytest.mark.parametrize("skill_name", list(EXPECTED_SKILLS))
def test_skill_metadata_and_structure(skill_name):
    skill_path = SKILLS_DIR / skill_name
    assert skill_path.is_dir()
    meta = load_skill_metadata(skill_path)
    assert meta is not None
    assert meta["name"] == skill_name
    assert len(meta["description"]) > 10
    skill_md = skill_path / "SKILL.md"
    assert skill_md.is_file()
    content = skill_md.read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "name: " + skill_name in content
    assert len(content) > 100
