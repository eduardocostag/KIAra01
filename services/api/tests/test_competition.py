import pytest

from kiara_api.competition import KiaraCompetitionInput, _kiara_public_target
from kiara_api.instagram_private import _profile
from kiara_api.http.errors import ApiError


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
