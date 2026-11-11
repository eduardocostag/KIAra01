from unittest.mock import AsyncMock

import pytest

from app.integrations.openwa import OpenWADeliveryUnknown, OpenWAError
from app.whatsapp.browser import BrowserNotReady
from app.whatsapp.openwa import OpenWABrowser


def client_fixture():
    client = AsyncMock()
    client.status.return_value = {"id": "session-1", "status": "ready", "engineLoaded": True}
    client.read_messages.return_value = [
        {"waMessageId": "m2", "body": "Olá", "direction": "incoming", "timestamp": 200},
        {"waMessageId": "m1", "body": "Bom dia", "direction": "outgoing", "timestamp": 100},
    ]
    client.send_text.return_value = {"message_id": "m3", "status": "accepted"}
    return client


@pytest.mark.asyncio
async def test_status_checks_live_engine_and_close_does_not_unlink():
    client = client_fixture()
    browser = OpenWABrowser(client, "session-1")
    assert await browser.status() == "ready"
    client.status.return_value["engineLoaded"] = False
    assert await browser.status() == "offline"
    client.status.return_value["status"] = "qr_ready"
    assert await browser.status() == "qr"
    client.status.side_effect = OpenWAError("unavailable")
    assert await browser.status() == "offline"
    await browser.start()
    await browser.close()
    client.start_session.assert_not_awaited()
    client.logout.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_sorts_history_uses_stable_provider_ids_and_no_extension():
    client = client_fixture()
    browser = OpenWABrowser(client, "session-1")
    assert await browser.read("5511999999999") == [
        {"id": "m1", "text": "Bom dia", "direction": "out"},
        {"id": "m2", "text": "Olá", "direction": "in"},
    ]
    client.read_messages.assert_awaited_once_with("session-1", "5511999999999", limit=100)


@pytest.mark.asyncio
async def test_new_human_message_blocks_send_and_never_guesses_lid_phone():
    client = client_fixture()
    browser = OpenWABrowser(client, "session-1")
    with pytest.raises(BrowserNotReady, match="mudou"):
        await browser.send("5511999999999", "Resposta", expected_ids=["m1"])
    client.send_text.assert_not_awaited()
    with pytest.raises(ValueError):
        await browser.read("12345@lid")


@pytest.mark.asyncio
async def test_confirmed_api_receipt_is_acceptance_not_delivery_and_not_retried():
    client = client_fixture()
    browser = OpenWABrowser(client, "session-1")
    assert await browser.send("5511999999999", "Resposta", expected_ids=["m1", "m2"]) == "m3"
    args = client.send_text.call_args
    assert args.args == ("session-1", "5511999999999", "Resposta")
    assert args.kwargs["idempotency_key"].startswith("kiara-")
    assert browser.receipt_semantics == "gateway_accepted"
    client.send_text.side_effect = OpenWADeliveryUnknown("unknown")
    with pytest.raises(OpenWADeliveryUnknown):
        await browser.send("5511999999999", "Resposta", expected_ids=["m1", "m2"])
    assert client.send_text.await_count == 2  # exactly one attempt per explicit call


@pytest.mark.asyncio
async def test_missing_body_in_snapshot_pauses_instead_of_skipping_human_message():
    client = client_fixture()
    client.read_messages.return_value.append({"waMessageId": "media", "direction": "outgoing", "body": None})
    browser = OpenWABrowser(client, "session-1")
    with pytest.raises(BrowserNotReady, match="incompleto"):
        await browser.send("5511999999999", "Resposta", expected_ids=["m1", "m2"])
    client.send_text.assert_not_awaited()
