from kiara_api import chat_actions


def test_known_sites_and_searches_become_buttons():
    text, actions = chat_actions.take_actions("Abrindo o YouTube. [[ABRIR: youtube | receita de bolo]] [[ABRIR: o GitHub]]")
    assert text == "Abrindo o YouTube."
    assert actions == [{"label": "YouTube: receita de bolo", "url": "https://www.youtube.com/results?search_query=receita+de+bolo"},
                       {"label": "GitHub", "url": "https://github.com"}]


def test_aliases_unknown_keys_and_limit():
    _, actions = chat_actions.take_actions("[[ABRIR: chrome]] [[ABRIR: cmd]] [[ABRIR: https://evil.example]] [[ABRIR: vs code]] [[ABRIR: zap]] [[ABRIR: gmail]]")
    assert [item["label"] for item in actions] == ["Nova aba", "VS Code", "WhatsApp Web"]
    assert all(not item["url"].startswith("https://evil") for item in actions)


def test_no_marker_no_action():
    assert chat_actions.take_actions("Oi! Tudo bem?") == ("Oi! Tudo bem?", [])


def test_voice_direct_model_goes_first_and_falls_back(monkeypatch):
    import asyncio
    from kiara_api import chat
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(chat, "_configuration", lambda: ("https://gateway.example/ai/v1", "main-model", "gw-key"))
    calls = []

    async def streamer(base, key, model, conversation, max_tokens, timeout):
        calls.append((base, key, model))
        if base == chat.GROQ_BASE_URL:
            raise RuntimeError("groq down")
        yield "Oi!"

    async def run():
        return [event async for event in chat.stream_conversation([{"role": "user", "content": "oi"}], streamer=streamer, fast=True)]

    events = asyncio.run(run())
    assert calls[0] == (chat.GROQ_BASE_URL, "test-key", chat.DEFAULT_GROQ_VOICE_MODEL)
    assert calls[1][0] == "https://gateway.example/ai/v1" and ("delta", "Oi!") in events
    calls.clear()
    asyncio.run(chat.stream_conversation([{"role": "user", "content": "oi"}], streamer=streamer, fast=False).__anext__())
    assert all(base != chat.GROQ_BASE_URL for base, _, _ in calls)       # only voice uses the direct model
