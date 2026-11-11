from unittest.mock import AsyncMock

import pytest

from app.whatsapp.browser import BrowserNotReady
from app.whatsapp.chatwoot_handoff import ChatwootHandoffGuard
from app.whatsapp.openwa import OpenWABrowser


def conversation(**changes):
    return {"id": 7, "inbox_id": 3, "status": "open", "assignee_id": None,
            "meta": {"sender": {"phone_number": "+55 (11) 99999-9999"}, "assignee": None},
            "custom_attributes": {}, **changes}


@pytest.mark.asyncio
async def test_unassigned_open_conversation_authorizes_only_target_inbox():
    client = AsyncMock()
    client.list_conversations.side_effect = [[conversation(), conversation(inbox_id=4)], []]
    await ChatwootHandoffGuard(client, 3)("5511999999999")
    assert client.list_conversations.await_count == 2
    assert client.list_conversations.call_args_list[0].kwargs == {"status": "all", "page": 1, "limit": 50}
    assert client.list_conversations.call_args_list[1].kwargs == {"status": "all", "page": 2, "limit": 50}


@pytest.mark.parametrize("change", [
    {"status": "resolved"}, {"status": "snoozed"}, {"assignee_id": 5},
    {"meta": {"sender": {"phone_number": "+5511999999999"}, "assignee": {"id": 8}}},
    {"custom_attributes": {"kiara_automation_enabled": False}},
    {"custom_attributes": {"kiara_automation_enabled": "false"}},
    {"custom_attributes": None},
])
@pytest.mark.asyncio
async def test_human_assignment_status_or_explicit_pause_blocks(change):
    client = AsyncMock()
    client.list_conversations.side_effect = [[conversation(**change)], []]
    with pytest.raises(BrowserNotReady):
        await ChatwootHandoffGuard(client, 3)("5511999999999")


@pytest.mark.parametrize("rows", [[], [conversation(), conversation(id=8)],
                                  [conversation(inbox_id=4)],
                                  [conversation(meta={"sender": {"phone_number": "123@lid"}})]])
@pytest.mark.asyncio
async def test_missing_ambiguous_other_inbox_and_lid_are_not_authorization(rows):
    client = AsyncMock()
    client.list_conversations.side_effect = [rows, []]
    with pytest.raises(BrowserNotReady):
        await ChatwootHandoffGuard(client, 3)("5511999999999")


@pytest.mark.asyncio
async def test_bounded_paging_refuses_an_incomplete_listing():
    client = AsyncMock()
    client.list_conversations.return_value = [conversation(inbox_id=4)] * 50
    with pytest.raises(BrowserNotReady):
        await ChatwootHandoffGuard(client, 3)("5511999999999")
    assert client.list_conversations.await_count == 5


@pytest.mark.asyncio
async def test_matching_contact_on_second_page_and_pending_are_supported():
    client = AsyncMock()
    client.list_conversations.side_effect = [[conversation(inbox_id=4)] * 50,
                                              [conversation(status="pending")], []]
    await ChatwootHandoffGuard(client, 3)("5511999999999")


@pytest.mark.asyncio
async def test_short_page_does_not_hide_a_duplicate_conversation_on_next_page():
    client = AsyncMock()
    client.list_conversations.side_effect = [[conversation()], [conversation(id=8)], []]
    with pytest.raises(BrowserNotReady, match="única"):
        await ChatwootHandoffGuard(client, 3)("5511999999999")
    assert client.list_conversations.await_count == 3


@pytest.mark.asyncio
async def test_five_short_nonempty_pages_still_require_review():
    client = AsyncMock()
    client.list_conversations.side_effect = [[conversation()]] + [[conversation(inbox_id=4)]] * 4
    with pytest.raises(BrowserNotReady, match="única"):
        await ChatwootHandoffGuard(client, 3)("5511999999999")
    assert client.list_conversations.await_count == 5


@pytest.mark.asyncio
async def test_api_failure_is_sanitized_and_blocks():
    client = AsyncMock()
    client.list_conversations.side_effect = RuntimeError("private-key")
    with pytest.raises(BrowserNotReady) as error:
        await ChatwootHandoffGuard(client, 3)("5511999999999")
    assert "private-key" not in str(error.value)


@pytest.mark.asyncio
async def test_authorizer_is_checked_after_snapshot_and_before_openwa_write():
    order = []
    client = AsyncMock()
    client.status.return_value = {"status": "ready", "engineLoaded": True}
    client.read_messages.return_value = [{"waMessageId": "m1", "body": "Oi", "direction": "incoming", "timestamp": 1}]

    async def authorize(phone):
        order.append("authorize")
        assert client.read_messages.await_count == 1
        client.send_text.assert_not_awaited()
        raise BrowserNotReady("human assigned")

    browser = OpenWABrowser(client, "session-1", send_authorizer=authorize)
    with pytest.raises(BrowserNotReady):
        await browser.send("5511999999999", "Oi", expected_ids=["m1"])
    assert order == ["authorize"]
    client.send_text.assert_not_awaited()
