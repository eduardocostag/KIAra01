"""Loader and catalog for development and operational skills under kiara_api.platform.skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

SKILLS_DIR = Path(__file__).resolve().parent


def load_skill_metadata(skill_folder: Path) -> dict[str, Any] | None:
    skill_file = skill_folder / "SKILL.md"
    if not skill_file.is_file():
        return None
    try:
        content = skill_file.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            name = meta.get("name", skill_folder.name)
            desc = meta.get("description", "")
            return {
                "name": name,
                "description": desc,
                "folder": skill_folder.name,
                "path": str(skill_file),
            }
    except Exception:
        pass
    return None


def get_platform_skills() -> list[dict[str, Any]]:
    skills = []
    if not SKILLS_DIR.is_dir():
        return skills
    for item in sorted(SKILLS_DIR.iterdir()):
        if item.is_dir():
            meta = load_skill_metadata(item)
            if meta:
                skills.append(meta)
    return skills
