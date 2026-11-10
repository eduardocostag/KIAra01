import json

import pytest

from app.tools.instagram_content import RESOURCE_ROOT, InstagramContentCheckTool


@pytest.mark.parametrize("operation", ["hookscore", "beats", "caption", "detect", "humanize"])
async def test_local_utilities(operation):
    result = await InstagramContentCheckTool().execute(
        operation=operation, text="I lost $18000 on one missing contract.\nHere is clause 4.")
    assert result.success
    assert json.loads(result.output)
    assert result.metadata["local_only"]


async def test_humanizer_removes_invisible_characters():
    result = await InstagramContentCheckTool().execute(operation="humanize", text="hello\u200b world")
    assert "\u200b" not in json.loads(result.output)["text"]


async def test_swipe_uses_account_median():
    result = await InstagramContentCheckTool().execute(operation="swipe", reels=[
        {"account": "@large", "hook": "How to fix contracts", "views": 1000000, "median": 2000000},
        {"account": "@small", "hook": "I lost $10000 yesterday", "views": 100000, "median": 1000},
    ])
    ranked = json.loads(result.output)["reels"]
    assert ranked[0]["account"] == "@small"
    assert ranked[0]["outlier"] == 100


@pytest.mark.parametrize("params", [
    {"operation": "../../bad", "text": "hello"},
    {"operation": "caption", "text": "x" * 12001},
    {"operation": "beats", "text": "hello", "wpm": 0},
    {"operation": "caption", "text": "hello", "out": "arbitrary"},
    {"operation": "swipe", "reels": [{"account": "x", "hook": "x", "views": -1}]},
])
async def test_rejects_invalid_inputs(params):
    with pytest.raises(ValueError):
        await InstagramContentCheckTool().execute(**params)


def test_all_thirteen_skills_and_reference_assets_present():
    assert len(list((RESOURCE_ROOT / "skills").glob("*/SKILL.md"))) == 13
    for path in ("LICENSE", "voice-template.md", "skills/ig-reel/hooks.json",
                 "skills/ig-profile/rubric.json", "skills/ig-human/slop.json"):
        assert (RESOURCE_ROOT / path).is_file()


def test_audit_omits_drafts():
    safe = InstagramContentCheckTool().audit_parameters({"operation": "caption", "text": "secret"})
    assert "secret" not in str(safe)
