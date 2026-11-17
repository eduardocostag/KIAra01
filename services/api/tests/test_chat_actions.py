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
