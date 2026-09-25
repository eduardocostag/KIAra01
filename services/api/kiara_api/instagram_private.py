from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


InstagramCollectionMode = Literal["account_audience", "account_commenters", "commenters"]


@dataclass(frozen=True)
class InstagramSessionFailure(Exception):
    status_code: int
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def _client(session_id: str):
    try:
        from instagrapi import Client
    except ImportError as error:
        raise InstagramSessionFailure(
            503,
            "instagram_collector_unavailable",
            "O coletor autenticado do Instagram ainda não está disponível neste servidor.",
        ) from error

    client = Client()
    client.request_timeout = 12
    try:
        client.login_by_sessionid(session_id)
    except Exception as error:  # instagrapi exposes multiple authentication exception classes
        raise _mapped_failure(error) from None
    return client


def _mapped_failure(error: Exception) -> InstagramSessionFailure:
    name = type(error).__name__
    if name in {"LoginRequired", "ClientLoginRequired", "ClientUnauthorizedError", "BadPassword"}:
        return InstagramSessionFailure(
            409,
            "instagram_session_expired",
            "A sessão do Instagram expirou. Atualize a conexão em Administração > APIs e conexões.",
        )
    if name in {"ChallengeRequired", "ChallengeUnknownStep", "CheckpointRequired", "TwoFactorRequired"}:
        return InstagramSessionFailure(
            409,
            "instagram_verification_required",
            "O Instagram solicitou uma verificação de segurança. Confirme o acesso no Instagram e reconecte a conta na Kiara.",
        )
    if name in {"PleaseWaitFewMinutes", "ClientThrottledError", "RateLimitError", "SentryBlock"}:
        return InstagramSessionFailure(
            429,
            "instagram_rate_limited",
            "O Instagram limitou temporariamente as consultas. Aguarde alguns minutos e tente novamente.",
        )
    if name in {"UserNotFound", "MediaNotFound"}:
        return InstagramSessionFailure(
            404,
            "instagram_target_not_found",
            "O perfil ou a publicação não foi encontrado. Confirme o @ ou o link informado.",
        )
    if name in {"PrivateError", "MediaUnavailable"}:
        return InstagramSessionFailure(
            422,
            "instagram_target_not_public",
            "O perfil ou a publicação não está acessível para a conta conectada.",
        )
    return InstagramSessionFailure(
        502,
        "instagram_collection_failed",
        "O Instagram não concluiu a consulta. Confirme a conexão da conta e tente novamente.",
    )


def verify_instagram_session(session_id: str) -> dict[str, Any]:
    client = _client(session_id)
    try:
        account = client.account_info()
    except Exception as error:
        raise _mapped_failure(error) from None
    return {
        "connected": True,
        "username": str(getattr(account, "username", "") or ""),
        "user_id": str(getattr(account, "pk", "") or getattr(client, "user_id", "") or ""),
    }


def _profile(user: Any, *, relationship: str, media: Any = None, comment: Any = None) -> dict[str, Any] | None:
    username = str(getattr(user, "username", "") or "").strip().lower()
    user_id = str(getattr(user, "pk", "") or "").strip()
    if not username or not user_id:
        return None
    media_code = str(getattr(media, "code", "") or "").strip()
    profile = {
        "id": f"instagram:{user_id}",
        "pk": user_id,
        "username": username,
        "full_name": str(getattr(user, "full_name", "") or "").strip(),
        "profile_url": f"https://www.instagram.com/{username}/",
        "relationship_type": relationship,
        "source_media_id": str(getattr(media, "pk", "") or ""),
        "source_media_url": f"https://www.instagram.com/p/{media_code}/" if media_code else "",
        "source": "kiara_instagram_authenticated",
    }
    if comment is not None:
        profile["comment_id"] = str(getattr(comment, "pk", "") or "")
        profile["comment_text"] = str(getattr(comment, "text", "") or "")[:500]
    return profile


def _add_profile(items: dict[str, dict[str, Any]], profile: dict[str, Any] | None, limit: int) -> None:
    if profile is None or len(items) >= limit:
        return
    identifier = profile["id"]
    current = items.get(identifier)
    if current is None:
        items[identifier] = profile
        return
    relationships = {str(current.get("relationship_type", "")), str(profile.get("relationship_type", ""))}
    relationships.discard("")
    current["relationship_type"] = ",".join(sorted(relationships))


def collect_instagram_relationships(
    session_id: str,
    mode: InstagramCollectionMode,
    target: str,
    *,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    client = _client(session_id)
    found: dict[str, dict[str, Any]] = {}
    media_count = 0
    try:
        if mode == "commenters":
            media_pk = client.media_pk_from_url(target)
            media = client.media_info(media_pk)
            media_count = 1
            for comment in client.media_comments(media_pk, amount=limit):
                _add_profile(found, _profile(comment.user, relationship="commented", media=media, comment=comment), limit)
        else:
            username = target.removeprefix("@").strip()
            user_id = client.user_id_from_username(username)
            medias = client.user_medias(user_id, amount=3)
            media_count = len(medias)
            for media in medias:
                if len(found) >= limit:
                    break
                for comment in client.media_comments(media.pk, amount=min(50, limit)):
                    _add_profile(found, _profile(comment.user, relationship="commented", media=media, comment=comment), limit)
                if mode == "account_audience" and len(found) < limit:
                    for user in client.media_likers(media.pk):
                        _add_profile(found, _profile(user, relationship="liked", media=media), limit)
                        if len(found) >= limit:
                            break
    except InstagramSessionFailure:
        raise
    except Exception as error:
        raise _mapped_failure(error) from None

    return list(found.values()), {
        "source": "kiara_instagram_authenticated",
        "evidence": "instagram_private_api_relationship",
        "mode": mode,
        "media_checked": media_count,
        "collected": len(found),
    }
