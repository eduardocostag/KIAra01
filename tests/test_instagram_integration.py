from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

import pytest

from app.integrations.instagram import (
    InstagramApiError,
    InstagramContractError,
    InstagramMessagingClient,
    parse_message_events,
    verify_webhook_challenge,
    verify_webhook_signature,
)


def test_webhook_handshake_and_signature_use_exact_bytes() -> None:
    assert verify_webhook_challenge(
        mode="subscribe", verify_token="token", challenge="opaque", expected_token="token"
    ) == "opaque"
    body = b'{"object":"instagram"}'
    digest = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    verify_webhook_signature(body, f"sha256={digest}", "secret")
    with pytest.raises(InstagramContractError):
        verify_webhook_signature(body + b" ", f"sha256={digest}", "secret")
    with pytest.raises(InstagramContractError):
        verify_webhook_signature(body, "sha256=not-a-digest", "secret")
    with pytest.raises(InstagramContractError):
        verify_webhook_signature(b"x" * (64 * 1024 + 1), f"sha256={digest}", "secret")


def test_parser_normalizes_messages_and_ignores_other_events() -> None:
    payload = {
        "object": "instagram",
        "entry": [{
            "id": "account",
            "messaging": [
                {"sender": {"id": "person"}, "recipient": {"id": "account"},
                 "timestamp": 123, "message": {"mid": "m1", "text": "Oi"}},
                {"sender": {"id": "person"}, "read": {"mid": "m1"}},
            ],
        }],
    }
    assert parse_message_events(payload)[0].message_id == "m1"
    assert parse_message_events(payload)[0].text == "Oi"


def test_parser_rejects_resource_abuse_and_drops_invalid_message_fields() -> None:
    with pytest.raises(InstagramContractError):
        parse_message_events({"object": "instagram", "entry": [{}] * 101})
    payload = {
        "object": "instagram",
        "entry": [{
            "id": "account",
            "messaging": [{
                "sender": {"id": "person"}, "recipient": {"id": "account"},
                "timestamp": 123, "message": {"mid": "m1", "text": "x" * 4097},
            }],
        }],
    }
    assert parse_message_events(payload) == []


@pytest.mark.parametrize("field,value", [
    ("timestamp", "not-an-integer"),
    ("timestamp", -1),
    ("sender", {}),
    ("recipient", {}),
])
def test_parser_ignores_incomplete_messages(field, value) -> None:
    event = {
        "sender": {"id": "person"}, "recipient": {"id": "account"},
        "timestamp": 123, "message": {"mid": "m1", "text": "Oi"},
    }
    event[field] = value
    payload = {"object": "instagram", "entry": [{"id": "account", "messaging": [event]}]}
    assert parse_message_events(payload) == []


@dataclass
class Response:
    status: int
    body: dict


class FakeHttp:
    def __init__(self) -> None:
        self.call = None

    async def request(self, method, url, **kwargs):
        self.call = (method, url, kwargs)
        return Response(200, {"recipient_id": "person", "message_id": "sent-1"})


class ErrorHttp:
    async def request(self, *_args, **_kwargs):
        return Response(429, {"error": {"message": "limit", "code": 4}})


async def test_send_text_uses_versioned_official_endpoint_and_payload() -> None:
    http = FakeHttp()
    client = InstagramMessagingClient(
        http, access_token="secret", api_version="v23.0", account_id="account"
    )
    assert await client.send_text("person", "Ola") == "sent-1"
    assert http.call == (
        "POST",
        "https://graph.instagram.com/v23.0/account/messages",
        {"token": "secret", "payload": {"recipient": {"id": "person"},
                                          "message": {"text": "Ola"}}},
    )


async def test_send_text_classifies_rate_limit_as_retryable() -> None:
    client = InstagramMessagingClient(
        ErrorHttp(), access_token="secret", api_version="v25.0", account_id="account"
    )
    with pytest.raises(InstagramApiError) as caught:
        await client.send_text("person", "Oi")
    assert caught.value.http_status == 429
    assert caught.value.retryable is True
