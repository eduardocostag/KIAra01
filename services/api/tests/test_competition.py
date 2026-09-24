import pytest

from kiara_api.competition import CompetitionAnalysisInput, _analysis_arguments, _decode_mcp_body
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
