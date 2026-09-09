"""Persist accepted Hunter discoveries into the CRM, in the caller's transaction.

Discovery is not consent, a WhatsApp account, or a conversation. No communication
records are created here, and re-discovery never resets a salesperson's stage.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, UUID, uuid5


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
    parts = urlsplit(value)
    host = (parts.hostname or "").lower().removeprefix("www.")
    port = f":{parts.port}" if parts.port and parts.port not in {80, 443} else ""
    query = urlencode(sorted((key, item) for key, item in parse_qsl(parts.query)
                             if not key.lower().startswith("utm_")
                             and key.lower() not in {"fbclid", "gclid", "ref", "hl", "authuser", "entry", "g_ep"}))
    return urlunsplit(("https", host + port, parts.path.rstrip("/") or "/", query, ""))


def _instagram_username(url: str) -> str | None:
    parts = urlsplit(url)
    if (parts.hostname or "").lower().removeprefix("www.") != "instagram.com":
        return None
    path = parts.path.strip("/").split("/")
    if len(path) != 1 or path[0].lower() in {"p", "reel", "reels", "explore", "stories", "accounts", "direct"}:
        return None
    return path[0].lower() if re.fullmatch(r"[a-zA-Z0-9_.]{1,30}", path[0]) else None


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
    for key in ("phone", "address", "website_evidence", "criterion_status", "place_id"):
        if isinstance(data.get(key), str) and data[key].strip():
            metadata[key] = data[key][:3000]
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
    status = (result.get("public_data") or {}).get("criterion_status")
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
                              saved_rows: list[dict[str, Any]]) -> dict[str, int]:
    """Upsert new accepted discoveries atomically alongside search completion.

    Only successful finish invokes this; merely reading old history never imports
    it. A per-tenant transaction lock serializes discovery aliases across searches.
    Existing CRM rows are locked and their stage, owners and permissions preserved.
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
        reason = _skip_reason(search_dict, result) or (None if keys else "invalid_source_url")
        if reason:
            summary["skipped"] += 1
            await _save_result_status(connection, org_uuid, search_dict["id"], result,
                                      {"crm_status": "skipped", "crm_skip_reason": reason})
            continue

        consumer_id = uuid5(NAMESPACE_URL, f"kiara:hunter-consumer:{org_uuid}:{keys[0]}")
        username = _instagram_username(result["url"])
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
        attrs["hunter"] = _hunter_metadata(search_dict, result, attrs.get("hunter"))
        if consumer:
            consumer_id = consumer["id"]
            await connection.execute(
                """UPDATE consumers SET attributes=%s,display_name=COALESCE(NULLIF(display_name,''),%s),
                   version=version+1,updated_at=now() WHERE organization_id=%s AND id=%s""",
                (json.dumps(attrs), result["title"][:500], org_uuid, consumer_id),
            )
        else:
            inserted = await (await connection.execute(
                """INSERT INTO consumers (organization_id,id,display_name,instagram_username,attributes)
                   VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id""",
                (org_uuid, consumer_id, result["title"][:500], username, json.dumps(attrs)),
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
                attrs["hunter"] = _hunter_metadata(search_dict, result, attrs.get("hunter"))
                await connection.execute(
                    """UPDATE consumers SET attributes=%s,display_name=COALESCE(NULLIF(display_name,''),%s),
                       version=version+1,updated_at=now() WHERE organization_id=%s AND id=%s""",
                    (json.dumps(attrs), result["title"][:500], org_uuid, consumer_id),
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
