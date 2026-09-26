import pytest

from kiara_api.competition import (
    CompetitionAnalysisInput,
    KiaraCompetitionInput,
    _analysis_arguments,
    _analysis_id,
    _decode_mcp_body,
    _items,
    _kiara_public_target,
)
from kiara_api.instagram_private import _profile
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


def test_kiara_authenticated_collector_accepts_posts_and_followers_mode() -> None:
    payload = KiaraCompetitionInput(mode="commenters", target="https://www.instagram.com/p/ABC_123/")
    assert _kiara_public_target(payload) == (payload.target, None)
    likes = KiaraCompetitionInput(mode="likers", target="https://www.instagram.com/reel/ABC_123/")
    assert _kiara_public_target(likes) == (likes.target, None)
    followers = KiaraCompetitionInput(mode="followers", target="@concorrente")
    assert _kiara_public_target(followers) == (
        "https://www.instagram.com/concorrente/",
        "concorrente",
    )


def test_kiara_prospect_requires_instagram_user_evidence() -> None:
    user = type("User", (), {"pk": "123", "username": "Pessoa.Um", "full_name": "Pessoa Um"})()
    media = type("Media", (), {"pk": "456", "code": "POST123"})()
    prospect = _profile(user, relationship="commented", media=media)
    assert prospect is not None
    assert prospect["id"] == "instagram:123"
    assert prospect["username"] == "pessoa.um"
    assert prospect["relationship_type"] == "commented"
    assert prospect["source_media_url"] == "https://www.instagram.com/p/POST123/"
    assert _profile(type("User", (), {"pk": "", "username": "popular"})(), relationship="liked") is None
