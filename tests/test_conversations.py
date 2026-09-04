from app.ui.conversations import ConversationStore


def test_conversation_store_deletes_only_selected_chat_and_persists(tmp_path) -> None:
    path = tmp_path / "conversations.json"
    store = ConversationStore(path)
    first = store.list()[0]
    second = store.create("Manter")

    assert store.delete(first["id"]) is True
    assert store.delete("inexistente") is False
    assert [item["id"] for item in store.list()] == [second["id"]]

    reopened = ConversationStore(path)
    assert [item["id"] for item in reopened.list()] == [second["id"]]
