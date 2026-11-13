"""Persist accepted Hunter discoveries into the CRM, in the caller's transaction.

Discovery is not consent, a WhatsApp account, or a conversation. No communication
records are created here, and re-discovery never resets a salesperson's stage.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

from .hunter_research import (
    canonical_public_identity,
    is_editorial_or_post,
    lead_requirement_gaps,
    normalize_result,
    result_niche_matches,
)


def _public_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value.strip())
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return None
        # Access port to reject malformed values before persisting the link.
        _ = parts.port
    except ValueError:
        return None
    return value.strip()[:3000]


def _canonical_url(value: str) -> str:
    return canonical_public_identity(value) or value


def _instagram_username(url: str) -> str | None:
    parts = urlsplit(url)
    if (parts.hostname or "").lower().removeprefix("www.") != "instagram.com":
        return None
    path = parts.path.strip("/").split("/")
    if len(path) != 1 or path[0].lower() in {"p", "reel", "reels", "explore", "stories", "accounts", "direct"}:
        return None
    return path[0].lower() if re.fullmatch(r"[a-zA-Z0-9_.]{1,30}", path[0]) else None


def _facebook_username(url: str) -> str | None:
    parts = urlsplit(url)
    if (parts.hostname or "").lower().removeprefix("www.") not in {"facebook.com", "fb.com"}:
        return None
    path = parts.path.strip("/").split("/")
    if not path or path == [""]:
        return None
    first = path[0].lower()
    if first in {
        "p", "posts", "photos", "videos", "watch", "groups", "events", "share",
        "sharer", "story.php", "permalink.php", "login", "help",
        "marketplace", "about", "policies", "recover", "settings",
    }:
        return None
    if first == "profile.php":
        from urllib.parse import parse_qs
        params = parse_qs(parts.query)
        uid = (params.get("id") or [""])[0]
        return uid if uid.isdigit() else None
    if len(path) == 1 and first not in {"pages", "people"} and re.fullmatch(r"[a-zA-Z0-9_.-]{1,60}", path[0]):
        return path[0].lower()
    if first in {"pages", "people"} and len(path) >= 2:
        return path[-1] if path[-1].isdigit() else path[1].lower()
    return None


def _consumer_display_name(result: dict[str, Any], username: str | None) -> str:
    """Return a human label, never the search-engine document title."""
    if username:
        return f"@{username}"[:500]
    if result.get("source") == "web":
        label = (result.get("public_data") or {}).get("display_name")
        if isinstance(label, str) and label.strip():
            return label.strip()[:500]
    title = str(result.get("title") or "")
    title = re.sub(r"\s*[•|·-]\s*Instagram(?:\s+photos?\s+and\s+videos?)?\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*Instagram\s+photos?\s+and\s+videos?\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*[•|·-]\s*Facebook(?:\s+p[aá]gina|\s+perfil)?\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*Facebook\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+[.…]{2,}\s*$", "", title).strip()
    return (title or "Contato sem nome")[:500]


def identity_keys(result: dict[str, Any]) -> list[str]:
    """Stable, tenant-independent aliases; the consumer UUID also includes tenant.

    A phone is intentionally not an identity: practices can share receptionists.
    """
    url = _public_url(result.get("url"))
    if not url:
        return []
    data = result.get("public_data") or {}
    keys: list[str] = []
    if result.get("source") == "google_maps":
        place_id = data.get("place_id")
        params = dict(parse_qsl(urlsplit(url).query))
        place_id = place_id or params.get("query_place_id") or params.get("place_id") or params.get("cid")
        token = re.search(r"!1s([^!/?&]+)", unquote(url))
        place_id = place_id or (token.group(1) if token else None)
        if isinstance(place_id, str) and place_id.strip():
            keys.append(f"google_maps:place:{place_id.strip()[:300]}")
    username = _instagram_username(url)
    if username:
        keys.append(f"instagram:{username}")
    fb_user = _facebook_username(url)
    if fb_user:
        keys.append(f"facebook:{fb_user}")
    keys.append(f"url:{_canonical_url(url)}")
    return list(dict.fromkeys(keys))


def _hunter_metadata(search: dict[str, Any], result: dict[str, Any], previous: Any = None) -> dict[str, Any]:
    data = result.get("public_data") or {}
    options = search.get("search_options") or search
    metadata = {
        "source": result["source"], "source_url": _public_url(result.get("url")),
        "search_id": str(search["id"]), "research_query": search["query"],
        "location": search.get("location"), "market": search.get("market"),
        "research_objective": options.get("objective", ""),
        "website_status": data.get("website_status", "unknown"),
    }
    for key in ("phone", "email", "address", "address_evidence", "address_source_url", "address_evidence_text",
                "website_evidence", "criterion_status", "place_id", "enrichment", "provider", "profile_bio",
                "bio_status", "page_status", "display_name", "source_title", "name_status"):
        if isinstance(data.get(key), str) and data[key].strip():
            metadata[key] = data[key][:3000]
    if result_niche_matches(result, search):
        metadata["niche_evidence_text"] = " ".join(str(result.get(key) or "") for key in ("title", "summary"))[:1500]
    for key in ("website_quality_score", "website_quality_signals", "match_reasons"):
        if data.get(key) is not None:
            metadata[key] = data[key]
    # Google reputation feeds the lead fit score.
    for key in ("rating", "user_rating_count"):
        if isinstance(data.get(key), (int, float)) and not isinstance(data.get(key), bool):
            metadata[key] = data[key]
    if isinstance(data.get("business_status"), str):
        metadata["business_status"] = data["business_status"][:40]
    for key in ("lead_tier", "temperature"):
        if isinstance(data.get(key), str):
            metadata[key] = data[key][:20]
    for key in ("detail_inspected", "bio_location_evidence", "bio_niche_evidence", "manual_lead_selection"):
        if isinstance(data.get(key), bool):
            metadata[key] = data[key]
    for key in ("website_url", "whatsapp_url"):
        value = _public_url(data.get(key))
        if value and (key != "whatsapp_url" or (urlsplit(value).hostname or "").lower()
                      in {"wa.me", "api.whatsapp.com", "www.whatsapp.com", "whatsapp.com"}):
            metadata[key] = value
    # Failure to find a contact again is not proof it no longer exists. Keep
    # previous observed contact details, but never carry over criterion claims.
    if isinstance(previous, dict):
        for key in ("phone", "whatsapp_url"):
            if key not in metadata and isinstance(previous.get(key), str):
                metadata[key] = previous[key]
    return metadata


def _skip_reason(search: dict[str, Any], result: dict[str, Any]) -> str | None:
    options = search.get("search_options") or search
    data = result.get("public_data") or {}
    if result.get("source") in {"instagram", "facebook"} and data.get("content_kind") == "publication":
        return "publication_not_contact"
    status = data.get("criterion_status")
    if status in {"rejected", "not_matched"}:
        return "criterion_not_matched"
    if status in {"not_verified", "unverified"}:
        return "criterion_not_verified"
    if options.get("research_mode") == "focused" and options.get("objective") and status not in {"matched", "verified"}:
        return "criterion_not_verified"
    return None


async def _save_result_status(connection: Any, org: UUID, search_id: Any,
                              result: dict[str, Any], updates: dict[str, Any]) -> None:
    result.setdefault("public_data", {}).update(updates)
    if updates.get("crm_status") == "synced":
        result["public_data"].pop("crm_skip_reason", None)
    else:
        result["public_data"].pop("lead_id", None)
        result["public_data"].pop("pipeline_entry_id", None)
    await connection.execute(
        """UPDATE hunter_results SET public_data=%s
           WHERE organization_id=%s AND search_id=%s AND id=%s""",
        (json.dumps(result["public_data"]), org, search_id, result["id"]),
    )


async def sync_hunter_results(connection: Any, org_uuid: UUID, search_dict: dict[str, Any],
                              saved_rows: list[dict[str, Any]], *, user_selected: bool = False) -> dict[str, int]:
    """Explicitly upsert selected discoveries into CRM/Pipeline.

    Search completion only persists Hunter results. ``user_selected`` allows a
    human to promote an unverified discovery, while structural/consent safety
    checks (valid source identity, publication-only result, blocked contact)
    remain mandatory.
    """
    summary = {"created": 0, "existing": 0, "skipped": 0}
    if not saved_rows:
        return summary
    if search_dict.get("organization_id") is not None and str(search_dict["organization_id"]) != str(org_uuid):
        raise ValueError("hunter_crm_tenant_mismatch")
    for result in saved_rows:
        if result.get("organization_id") is not None and str(result["organization_id"]) != str(org_uuid):
            raise ValueError("hunter_crm_tenant_mismatch")
        if result.get("search_id") is not None and str(result["search_id"]) != str(search_dict["id"]):
            raise ValueError("hunter_crm_search_mismatch")
    lock_key = int.from_bytes(hashlib.sha256(f"hunter-crm:{org_uuid}".encode()).digest()[:8], "big", signed=True)
    await connection.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))
    for result in saved_rows:
        keys = identity_keys(result)
        normalized_result = normalize_result(result)
        missing_requirements = lead_requirement_gaps(normalized_result, search_dict)
        if not result_niche_matches(normalized_result, search_dict):
            missing_requirements.append("niche_match")
        criterion_reason = _skip_reason(search_dict, normalized_result)
        if user_selected and criterion_reason in {"criterion_not_matched", "criterion_not_verified"}:
            criterion_reason = None
            result.setdefault("public_data", {})["manual_lead_selection"] = True
            normalized_result["public_data"]["manual_lead_selection"] = True
        # A human can override an unverified commercial criterion, but never
        # structural requirements. Evaluate those independently: an earlier
        # criterion failure must not hide a missing phone, city or identity.
        # A person may add a lead that is not fully confirmed (tier Provável/A conferir): only the
        # business name and a public source stay mandatory. Automatic imports keep every requirement.
        if user_selected and not {"name", "source_url", "niche_match"} & set(missing_requirements):
            missing_requirements = []
        reason = (
            (None if keys else "invalid_source_url")
            or ("publication_not_contact" if is_editorial_or_post(normalized_result)
                or normalized_result["public_data"].get("content_kind") == "publication" else None)
            or (None if not missing_requirements else "incomplete_lead")
            or criterion_reason
        )
        if reason:
            summary["skipped"] += 1
            updates = {"crm_status": "skipped", "crm_skip_reason": reason}
            if reason == "incomplete_lead":
                updates["lead_requirements_missing"] = missing_requirements
            await _save_result_status(connection, org_uuid, search_dict["id"], result, updates)
            continue

        consumer_id = uuid5(NAMESPACE_URL, f"kiara:hunter-consumer:{org_uuid}:{keys[0]}")
        username = _instagram_username(result["url"])
        display_name = _consumer_display_name(normalized_result, username)
        consumer = await (await connection.execute(
            """SELECT id,display_name,attributes,consent_status,lifecycle_status FROM consumers
               WHERE organization_id=%s AND
                 (id=%s OR (attributes->'hunter_identity_keys') ?| %s::text[] OR lower(instagram_username)=%s)
               ORDER BY (lifecycle_status<>'active' OR consent_status IN ('revoked','opted_out')) DESC,
                        created_at,id LIMIT 1 FOR UPDATE""",
            (org_uuid, consumer_id, keys, username),
        )).fetchone()
        if consumer and (consumer["lifecycle_status"] != "active"
                         or consumer["consent_status"] in {"revoked", "opted_out"}):
            summary["skipped"] += 1
            await _save_result_status(connection, org_uuid, search_dict["id"], result,
                                      {"crm_status": "skipped", "crm_skip_reason": "contact_restricted"})
            continue

        attrs = dict(consumer["attributes"] or {}) if consumer else {}
        old_keys = attrs.get("hunter_identity_keys")
        attrs["hunter_identity_keys"] = list(dict.fromkeys((old_keys if isinstance(old_keys, list) else []) + keys))
        # Replace only discovery metadata. Manual CRM attributes and consent stay intact.
        attrs["hunter"] = _hunter_metadata(search_dict, normalized_result, attrs.get("hunter"))
        if consumer:
            consumer_id = consumer["id"]
            await connection.execute(
                """UPDATE consumers SET attributes=%s,display_name=COALESCE(NULLIF(display_name,''),%s),
                   version=version+1,updated_at=now() WHERE organization_id=%s AND id=%s""",
                (json.dumps(attrs), display_name, org_uuid, consumer_id),
            )
        else:
            inserted = await (await connection.execute(
                """INSERT INTO consumers (organization_id,id,display_name,instagram_username,attributes)
                   VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id""",
                (org_uuid, consumer_id, display_name, username, json.dumps(attrs)),
            )).fetchone()
            if not inserted:
                # Another writer (e.g. inbound Instagram ingestion) can create this
                # contact without the discovery lock. Re-read, never bypass controls.
                consumer = await (await connection.execute(
                    """SELECT id,display_name,attributes,consent_status,lifecycle_status FROM consumers
                       WHERE organization_id=%s AND (id=%s OR lower(instagram_username)=%s)
                       ORDER BY created_at,id LIMIT 1 FOR UPDATE""",
                    (org_uuid, consumer_id, username),
                )).fetchone()
                if not consumer or consumer["lifecycle_status"] != "active" or consumer["consent_status"] in {"revoked", "opted_out"}:
                    summary["skipped"] += 1
                    await _save_result_status(connection, org_uuid, search_dict["id"], result,
                                              {"crm_status": "skipped", "crm_skip_reason": "contact_restricted"})
                    continue
                consumer_id = consumer["id"]
                attrs = dict(consumer["attributes"] or {})
                old_keys = attrs.get("hunter_identity_keys")
                attrs["hunter_identity_keys"] = list(dict.fromkeys((old_keys if isinstance(old_keys, list) else []) + keys))
                attrs["hunter"] = _hunter_metadata(search_dict, normalized_result, attrs.get("hunter"))
                await connection.execute(
                    """UPDATE consumers SET attributes=%s,display_name=COALESCE(NULLIF(display_name,''),%s),
                       version=version+1,updated_at=now() WHERE organization_id=%s AND id=%s""",
                    (json.dumps(attrs), display_name, org_uuid, consumer_id),
                )

        entry = await (await connection.execute(
            """INSERT INTO pipeline_entries (organization_id,consumer_id,stage,next_action)
               VALUES (%s,%s,'new','Revisar contato público e planejar abordagem')
               ON CONFLICT (organization_id,consumer_id) DO NOTHING RETURNING id""",
            (org_uuid, consumer_id),
        )).fetchone()
        if entry:
            summary["created"] += 1
        else:
            entry = await (await connection.execute(
                "SELECT id FROM pipeline_entries WHERE organization_id=%s AND consumer_id=%s",
                (org_uuid, consumer_id),
            )).fetchone()
            summary["existing"] += 1
        if not entry:
            raise RuntimeError("hunter_crm_entry_missing")
        await _save_result_status(connection, org_uuid, search_dict["id"], result, {
            "lead_id": str(consumer_id), "pipeline_entry_id": str(entry["id"]), "crm_status": "synced",
        })
    return summary
