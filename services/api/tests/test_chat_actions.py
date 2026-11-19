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

    monkeypatch.setattr(chat, "VOICE_DIRECT_HEDGE_SECONDS", 0.0)
    events = asyncio.run(run())
    assert calls[0][0] == "https://gateway.example/ai/v1"                     # the smart server model starts first
    assert calls[1] == (chat.GROQ_BASE_URL, "test-key", chat.DEFAULT_GROQ_VOICE_MODEL) and ("delta", "Oi!") in events
    calls.clear()
    asyncio.run(chat.stream_conversation([{"role": "user", "content": "oi"}], streamer=streamer, fast=False).__anext__())
    assert all(base != chat.GROQ_BASE_URL for base, _, _ in calls)       # only voice uses the direct model



def test_voice_races_the_direct_model_against_the_server_and_the_fastest_speaks():
    import asyncio
    from kiara_api import chat

    async def run(slow_direct: bool, hedge: float = 0.0):
        chat.VOICE_DIRECT_HEDGE_SECONDS = hedge
        calls = []

        async def streamer(base, key, model, conversation, max_tokens, timeout):
            calls.append(model)
            await asyncio.sleep(0.3 if (model == "direct-model") == slow_direct else 0.01)
            yield f"Oi de {model}."
            yield " Tudo bem?"

        import os
        os.environ["KIARA_VOICE_DIRECT_API_KEY"] = "k"
        os.environ["KIARA_VOICE_DIRECT_BASE_URL"] = "https://direct.example/v1"
        os.environ["KIARA_VOICE_DIRECT_MODEL"] = "direct-model"
        try:
            chat._configuration = lambda: ("https://gateway.example/ai/v1", "main-model", "gw-key")
            events = [e async for e in chat.stream_conversation([{"role": "user", "content": "oi"}], streamer=streamer, fast=True)]
        finally:
            for name in ("KIARA_VOICE_DIRECT_API_KEY", "KIARA_VOICE_DIRECT_BASE_URL", "KIARA_VOICE_DIRECT_MODEL"):
                os.environ.pop(name, None)
        return calls, events

    original = chat._configuration
    try:
        calls, events = asyncio.run(run(slow_direct=True))
        assert calls[1] == "direct-model" and len(calls) == 2                 # both started (no hedge delay)
        assert events[0] == ("model", calls[0]) and "".join(t for k, t in events if k == "delta") == f"Oi de {calls[0]}. Tudo bem?"
        calls, events = asyncio.run(run(slow_direct=False))
        assert events[0] == ("model", "direct-model")
        assert [e for e in events if e[0] == "reset"] == []
        calls, events = asyncio.run(run(slow_direct=False, hedge=1.0))   # the server answers before the hedge
        assert calls == ["main-model"] or calls[0] != "direct-model"
        assert events[0][0] == "model" and events[0][1] != "direct-model"
    finally:
        chat._configuration = original
        chat.VOICE_DIRECT_HEDGE_SECONDS = 2.5


def test_ai_answers_queue_and_then_say_busy_instead_of_piling_up(monkeypatch):
    import asyncio
    from kiara_api import chat
    monkeypatch.setattr(chat, "AI_CONCURRENCY", 1)
    monkeypatch.setattr(chat, "AI_QUEUE_SECONDS", 0.05)
    monkeypatch.setattr(chat, "_AI_SLOTS", {})
    monkeypatch.setattr(chat, "_configuration", lambda: ("https://gateway.example/ai/v1", "main-model", "gw-key"))
    monkeypatch.delenv("KIARA_VOICE_DIRECT_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    async def slow(base, key, model, conversation, max_tokens, timeout):
        await asyncio.sleep(0.3)
        yield "Oi!"

    async def run():
        first = asyncio.ensure_future(chat.stream_conversation([{"role": "user", "content": "oi"}], streamer=slow).__anext__())
        await asyncio.sleep(0.01)                                   # the only slot is taken
        try:
            await chat.stream_conversation([{"role": "user", "content": "oi"}], streamer=slow).__anext__()
        except chat.AiBusyError:
            busy = True
        else:
            busy = False
        assert await first == ("model", "main-model")
        return busy

    assert asyncio.run(run()) is True
