import pytest

from kiara_api.competition import (
    CompetitionAnalysisInput,
    _analysis_arguments,
    _analysis_id,
    _decode_mcp_body,
    _imported_profile,
    _items,
    _normalize_imported_profiles,
)
from kiara_api.http.errors import ApiError


def test_competition_builds_instagram_followers_analysis() -> None:
    payload = CompetitionAnalysisInput(mode="followers", target="@kiara.test", name="Teste")
    assert _analysis_arguments(payload) == {
        "sourceType": "instagram", "mode": "followers", "username": "kiara.test", "name": "Teste",
    }


def test_competition_accepts_public_instagram_post() -> None:
    payload = CompetitionAnalysisInput(mode="commenters", target="https://www.instagram.com/reel/ABC123/")
    assert _analysis_arguments(payload)["postUrl"] == payload.target


@pytest.mark.parametrize("target", ["private user", "https://facebook.com/post/1", "https://instagram.com/profile"])
def test_competition_rejects_invalid_targets(target: str) -> None:
    mode = "commenters" if target.startswith("http") else "followers"
    with pytest.raises(ApiError):
        _analysis_arguments(CompetitionAnalysisInput(mode=mode, target=target))


def test_mcp_sse_response_is_decoded() -> None:
    assert _decode_mcp_body('event: message\ndata: {"result":{"ok":true}}\n') == {"result": {"ok": True}}


def test_competition_extracts_nested_analysis_and_prospects() -> None:
    assert _analysis_id({"data": {"analysis": {"analysisId": "analysis-123"}}}) == "analysis-123"
    assert _items({"result": {"prospects": [{"username": "kiara"}]}}, "prospects", "items") == [
        {"username": "kiara"}
    ]


def test_competition_normalizes_public_instagram_profiles() -> None:
    assert _imported_profile("https://www.instagram.com/Kiara.Test/ | Kiara Test") == {
        "id": "instagram:kiara.test",
        "username": "kiara.test",
        "full_name": "Kiara Test",
        "profile_url": "https://www.instagram.com/kiara.test/",
        "source": "kiara_public",
    }


def test_competition_import_deduplicates_and_rejects_non_profiles() -> None:
    result = _normalize_imported_profiles([
        "@Kiara.Test", "kiara.test", "https://instagram.com/KIARA.TEST/", "https://example.com/user", "https://instagram.com/reel/abc",
    ])
    assert [item["username"] for item in result] == ["kiara.test"]
