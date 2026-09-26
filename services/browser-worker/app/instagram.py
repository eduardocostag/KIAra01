from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


InstagramCollectionMode = Literal[
    "followers", "account_audience", "account_commenters", "commenters", "likers", "post_audience"
]
_MOBILE_BASE = "https://i.instagram.com/api/v1"
_WEB_BASE = "https://www.instagram.com/api/v1"
_WEB_PROFILE = f"{_WEB_BASE}/users/web_profile_info/"
_USER_AGENT = (
    "Instagram 309.0.0.40.113 Android (33/13; 420dpi; 1080x1920; "
    "Google; Pixel 6; oriole; tensor; pt_BR; 541635249)"
)


@dataclass(frozen=True)
class InstagramSessionFailure(Exception):
    status_code: int
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def _headers(session_id: str, *, web: bool = False) -> dict[str, str]:
    cookie_header = session_id if ";" in session_id else f"sessionid={session_id}"
    cookies = dict(
        part.strip().split("=", 1)
        for part in cookie_header.split(";")
        if "=" in part
    )
    headers = {
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        "Cookie": cookie_header,
        "Referer": "https://www.instagram.com/",
        "Origin": "https://www.instagram.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
            if web else _USER_AGENT
        ),
        "X-ASBD-ID": "129477",
        "X-IG-App-ID": "936619743392459" if web else "567067343352427",
        "X-IG-WWW-Claim": "0",
        "X-Requested-With": "XMLHttpRequest",
    }
    if cookies.get("csrftoken"):
        headers["X-CSRFToken"] = cookies["csrftoken"]
    return headers


def _failure_for_payload(data: dict[str, Any], default: InstagramSessionFailure) -> InstagramSessionFailure:
    message = str(data.get("message") or "").lower()
    if "login_required" in message or "not authorized" in message:
        return InstagramSessionFailure(
            409,
            "instagram_session_expired",
            "A sessão do Instagram expirou. Atualize a conexão em Administração > APIs e conexões.",
        )
    if "challenge" in message or "checkpoint" in message:
        return InstagramSessionFailure(
            409,
            "instagram_verification_required",
            "O Instagram solicitou uma verificação de segurança. Confirme o acesso no Instagram e reconecte a conta na Kiara.",
        )
    if "wait" in message or "rate" in message:
        return InstagramSessionFailure(
            429,
            "instagram_rate_limited",
            "O Instagram limitou temporariamente as consultas. Aguarde alguns minutos e tente novamente.",
        )
    raw_message = str(data.get("message") or "").strip()
    safe_message = raw_message[:200] if raw_message else "O Instagram recusou a consulta."
    return InstagramSessionFailure(default.status_code, default.code, safe_message)


def _json_get(
    url: str,
    session_id: str,
    *,
    max_bytes: int = 4_000_000,
    web: bool = False,
) -> dict[str, Any]:
    request = Request(url, headers=_headers(session_id, web=web))
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read(max_bytes + 1)
    except HTTPError as error:
        if error.code in {301, 302, 303, 307, 308, 401, 403}:
            raise InstagramSessionFailure(
                409,
                "instagram_session_expired",
                "A sessão do Instagram não foi aceita. Reconecte a conta e confirme que o feed abriu antes de concluir.",
            ) from None
        if error.code == 404:
            raise InstagramSessionFailure(
                404,
                "instagram_target_not_found",
                "O perfil ou a publicação não foi encontrado. Confirme o @ informado.",
            ) from None
        if error.code == 429:
            raise InstagramSessionFailure(
                429,
                "instagram_rate_limited",
                "O Instagram limitou temporariamente as consultas. Aguarde alguns minutos e tente novamente.",
            ) from None
        raise InstagramSessionFailure(
            502, "instagram_collection_failed", f"O Instagram respondeu com HTTP {error.code}."
        ) from None
    except (URLError, TimeoutError, OSError):
        raise InstagramSessionFailure(
            502,
            "instagram_unavailable",
            "O Instagram não respondeu à consulta. Tente novamente em alguns minutos.",
        ) from None
    if len(raw) > max_bytes:
        raise InstagramSessionFailure(502, "instagram_response_too_large", "A resposta do Instagram excedeu o limite seguro.")
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise InstagramSessionFailure(502, "instagram_invalid_response", "O Instagram respondeu em formato incompatível.") from None
    if not isinstance(data, dict):
        raise InstagramSessionFailure(502, "instagram_invalid_response", "O Instagram respondeu em formato incompatível.")
    if data.get("status") == "fail":
        raise _failure_for_payload(
            data,
            InstagramSessionFailure(502, "instagram_collection_failed", "O Instagram recusou a consulta."),
        )
    return data


def verify_instagram_session(session_id: str) -> dict[str, Any]:
    data = _json_get(f"{_MOBILE_BASE}/accounts/current_user/?edit=true", session_id)
    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    user_id = str(user.get("pk") or user.get("pk_id") or "")
    if not user_id:
        raise InstagramSessionFailure(409, "instagram_session_expired", "A sessão do Instagram não retornou uma conta válida.")
    return {"connected": True, "username": str(user.get("username") or ""), "user_id": user_id}


def _profile_info(session_id: str, username: str) -> dict[str, Any]:
    data = _json_get(f"{_WEB_PROFILE}?username={quote(username)}", session_id)
    nested = data.get("data") if isinstance(data.get("data"), dict) else {}
    user = nested.get("user") if isinstance(nested.get("user"), dict) else {}
    if not user:
        raise InstagramSessionFailure(404, "instagram_target_not_found", "O perfil informado não foi encontrado.")
    return user


def _image_url(item: dict[str, Any]) -> str:
    versions = item.get("image_versions2") if isinstance(item.get("image_versions2"), dict) else {}
    candidates = versions.get("candidates") if isinstance(versions.get("candidates"), list) else []
    for candidate in candidates:
        if isinstance(candidate, dict) and isinstance(candidate.get("url"), str):
            return candidate["url"]
    carousel = item.get("carousel_media") if isinstance(item.get("carousel_media"), list) else []
    return _image_url(carousel[0]) if carousel and isinstance(carousel[0], dict) else ""


def load_instagram_profile(session_id: str, username: str, *, media_limit: int = 12) -> dict[str, Any]:
    clean_username = username.removeprefix("@").strip()
    user = _profile_info(session_id, clean_username)
    user_id = str(user.get("id") or user.get("pk") or "")
    feed = _json_get(f"{_MOBILE_BASE}/feed/user/{quote(user_id)}/?count={media_limit}", session_id)
    items = feed.get("items") if isinstance(feed.get("items"), list) else []
    publications = []
    for item in items[:media_limit]:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "")
        media_id = str(item.get("pk") or item.get("id") or "").split("_", 1)[0]
        if not code or not media_id:
            continue
        caption = item.get("caption") if isinstance(item.get("caption"), dict) else {}
        product_type = str(item.get("product_type") or "")
        media_type = int(item.get("media_type") or 0)
        taken_at = item.get("taken_at")
        publications.append({
            "id": media_id,
            "code": code,
            "url": f"https://www.instagram.com/{'reel' if product_type == 'clips' else 'p'}/{code}/",
            "thumbnail_url": _image_url(item),
            "caption": str(caption.get("text") or "")[:240],
            "like_count": int(item.get("like_count") or 0),
            "comment_count": int(item.get("comment_count") or 0),
            "media_type": "video" if media_type == 2 else "carousel" if media_type == 8 else "image",
            "taken_at": datetime.fromtimestamp(taken_at, tz=timezone.utc).isoformat() if isinstance(taken_at, (int, float)) else None,
        })
    return {
        "profile": {
            "id": user_id,
            "username": str(user.get("username") or clean_username),
            "full_name": str(user.get("full_name") or ""),
            "biography": str(user.get("biography") or "")[:500],
            "profile_pic_url": str(user.get("profile_pic_url_hd") or user.get("profile_pic_url") or ""),
            "is_verified": bool(user.get("is_verified")),
            "is_private": bool(user.get("is_private")),
            "follower_count": int(user.get("edge_followed_by", {}).get("count") or user.get("follower_count") or 0),
            "following_count": int(user.get("edge_follow", {}).get("count") or user.get("following_count") or 0),
            "media_count": int(user.get("edge_owner_to_timeline_media", {}).get("count") or user.get("media_count") or 0),
        },
        "publications": publications,
    }


def _value(value: Any, name: str, default: Any = "") -> Any:
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _profile(user: Any, *, relationship: str, media: Any = None, comment: Any = None) -> dict[str, Any] | None:
    username = str(_value(user, "username") or "").strip().lower()
    user_id = str(_value(user, "pk") or _value(user, "id") or "").strip()
    if not username or not user_id:
        return None
    media_code = str(_value(media, "code") or "").strip()
    profile = {
        "id": f"instagram:{user_id}",
        "pk": user_id,
        "username": username,
        "full_name": str(_value(user, "full_name") or "").strip(),
        "profile_url": f"https://www.instagram.com/{username}/",
        "relationship_type": relationship,
        "source_media_id": str(_value(media, "pk") or _value(media, "id") or ""),
        "source_media_url": f"https://www.instagram.com/p/{media_code}/" if media_code else "",
        "source": "kiara_instagram_authenticated",
    }
    if comment is not None:
        profile["comment_id"] = str(_value(comment, "pk") or _value(comment, "id") or "")
        profile["comment_text"] = str(_value(comment, "text") or "")[:500]
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


def collect_instagram_followers(
    username: str,
    payload: dict[str, Any],
    *,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    users = payload.get("users") if isinstance(payload.get("users"), list) else []
    found: dict[str, dict[str, Any]] = {}
    for user in users:
        if isinstance(user, dict):
            _add_profile(found, _profile(user, relationship="follows"), limit)
        if len(found) >= limit:
            break
    return list(found.values()), {
        "source": "kiara_instagram_authenticated",
        "evidence": "instagram_followers_relationship",
        "mode": "followers",
        "target": username,
        "collected": len(found),
        "next_max_id": str(payload.get("next_max_id") or ""),
    }


def collect_instagram_relationships(
    session_id: str,
    mode: InstagramCollectionMode,
    target: str,
    *,
    media_id: str | None = None,
    limit: int = 100,
    comments_override: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if mode not in {"commenters", "likers", "post_audience"} or not media_id:
        raise InstagramSessionFailure(422, "instagram_publication_required", "Selecione uma publicação do perfil antes de extrair interações.")
    media_data = _json_get(f"{_MOBILE_BASE}/media/{quote(media_id, safe='_')}/info/", session_id)
    media_items = media_data.get("items") if isinstance(media_data.get("items"), list) else []
    media = media_items[0] if media_items and isinstance(media_items[0], dict) else {"id": media_id}
    found: dict[str, dict[str, Any]] = {}
    comments_available = True
    comment_limit = limit if mode == "commenters" else max(1, limit // 2)
    if mode in {"commenters", "post_audience"}:
        comments_data: dict[str, Any] = comments_override or {}
        comment_urls = (
            f"{_MOBILE_BASE}/media/{quote(media_id, safe='_')}/comments/?can_support_threading=true&permalink_enabled=false&min_id=0",
            f"{_WEB_BASE}/media/{quote(media_id, safe='_')}/comments/?can_support_threading=true&permalink_enabled=false&min_id=0",
            f"{_WEB_BASE}/media/{quote(media_id, safe='_')}/comments/?can_support_threading=true&permalink_enabled=false",
        )
        last_comment_error: InstagramSessionFailure | None = None
        if comments_override is None:
            for index, comments_url in enumerate(comment_urls):
                try:
                    comments_data = _json_get(
                        comments_url,
                        session_id,
                        web=index >= 1,
                    )
                    last_comment_error = None
                    break
                except InstagramSessionFailure as error:
                    last_comment_error = error
                    if error.code not in {"instagram_collection_failed", "instagram_invalid_response"}:
                        raise
        if last_comment_error is not None:
            # Algumas publicações permitem curtidas, mas bloqueiam a listagem de
            # comentários em todos os endpoints conhecidos.
            comments_available = False
        comments = comments_data.get("comments") if isinstance(comments_data.get("comments"), list) else []
        for comment in comments:
            if not isinstance(comment, dict):
                continue
            _add_profile(found, _profile(comment.get("user", {}), relationship="commented", media=media, comment=comment), comment_limit)
            if len(found) >= comment_limit:
                break
    if mode in {"likers", "post_audience"} and len(found) < limit:
        likers_data = _json_get(f"{_MOBILE_BASE}/media/{quote(media_id, safe='_')}/likers/", session_id)
        users = likers_data.get("users") if isinstance(likers_data.get("users"), list) else []
        for user in users:
            if isinstance(user, dict):
                _add_profile(found, _profile(user, relationship="liked", media=media), limit)
            if len(found) >= limit:
                break
    return list(found.values()), {
        "source": "kiara_instagram_authenticated",
        "evidence": "instagram_private_api_relationship",
        "mode": mode,
        "media_checked": 1,
        "media_id": media_id,
        "target": target,
        "comments_available": comments_available,
        "collected": len(found),
    }
