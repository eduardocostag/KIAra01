import pytest

from kiara_api.competition import (
    CompetitionAnalysisInput,
    KiaraCompetitionInput,
    _analysis_arguments,
    _analysis_id,
    _decode_mcp_body,
    _items,
    _kiara_public_target,
    _profiles_from_public_links,
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


def test_kiara_serverless_accepts_public_post_and_rejects_followers_mode() -> None:
    payload = KiaraCompetitionInput(mode="commenters", target="https://www.instagram.com/p/ABC_123/")
    assert _kiara_public_target(payload) == (payload.target, None)
    with pytest.raises(ValueError):
        KiaraCompetitionInput(mode="followers", target="@concorrente")


def test_kiara_serverless_extracts_only_profile_links() -> None:
    profiles = _profiles_from_public_links([
        "https://www.instagram.com/Pessoa.Um/",
        "https://instagram.com/pessoa.um/",
        "https://www.instagram.com/p/POST/",
        "https://example.com/pessoa",
        "https://www.instagram.com/concorrente/",
    ], excluded_username="concorrente")
    assert profiles == [{
        "id": "instagram:pessoa.um",
        "username": "pessoa.um",
        "profile_url": "https://www.instagram.com/pessoa.um/",
        "source": "kiara_public_serverless",
    }]
