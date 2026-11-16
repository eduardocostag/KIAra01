from fastapi import FastAPI
from fastapi.testclient import TestClient

from kiara_api import chat, memory
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.sdr import reply_prompt
from tests.test_chat_stream import events


def test_markers_are_taken_out_and_secrets_never_kept():
    text, remember, forget = memory.take_markers(
        "Anotado!\n[[LEMBRAR: Ana é dona da Clínica Sorriso em Porto Alegre]]\n[[LEMBRAR: a senha do banco é 1234]]"
        "\n[[LEMBRAR: cartão 4111 1111 1111 1111]]\n[[ESQUECER: preço antigo]]")
    assert text == "Anotado!"
    assert remember == ["Ana é dona da Clínica Sorriso em Porto Alegre"]
    assert forget == ["preço antigo"]


def test_contact_memory_merges_newest_first_without_duplicates():
    merged = memory.merge_contact_memory(["Quer site com agenda", "Mora em Canoas"], ["quer site com agenda", "Orçamento até R$ 2 mil", "token sk-abcdefghijk"])
    assert merged == ["quer site com agenda", "Orçamento até R$ 2 mil", "Mora em Canoas"]
    assert len(memory.merge_contact_memory([], [f"fato {n}" for n in range(40)])) == memory.CONTACT_FACTS


def test_reply_prompt_carries_contact_memory():
    system = reply_prompt("Lume, sites", "Ana", "Ana: oi", 0, ["Ana tem uma clínica"])[0]["content"]
    assert "O que você já sabe deste contato" in system and "- Ana tem uma clínica" in system
    assert "O que você já sabe" not in reply_prompt("Lume", "Ana", "Ana: oi")[0]["content"]


class FakeMemory:
    def __init__(self, facts):
        self.stored, self.forgotten, self.known = [], [], facts

    async def facts(self, organization_id):
        return self.known

    async def remember(self, organization_id, facts, source="chat"):
        self.stored.extend(facts)
        return len(facts)

    async def forget(self, organization_id, subjects):
        self.forgotten.extend(subjects)
        return len(subjects)


def build(monkeypatch, script, store, role="owner"):
    monkeypatch.setenv("KIARA_CHAT_API_BASE_URL", "")
    monkeypatch.setenv("KIARA_CHAT_API_KEY", "")
    monkeypatch.setenv("KIARA_CHAT_MODEL", "claude/claude-sonnet-5-5")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_URL", "https://kiara-debian.example.ts.net")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_TOKEN", "gw")
    monkeypatch.setenv("KIARA_CHAT_FALLBACKS", "")
    seen = []

    async def streamer(base, key, model, conversation, max_tokens, timeout):
        seen.append(conversation)
        for piece in script:
            yield piece

    app = FastAPI()
    app.include_router(chat.create_chat_router(streamer=streamer, memory=store))
    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", "org", "m", role, "req", email="admin@kiara.local")
    return TestClient(app), seen


def test_chat_remembers_and_uses_what_it_learned(monkeypatch):
    store = FakeMemory(["O dono se chama Eduardo"])
    api, seen = build(monkeypatch, ["Prazer, Ana! Vou lembrar.", "\n[[LEMBRAR: A pessoa se chama Ana]]"], store)
    got = events(api, {"messages": [{"role": "user", "content": "Me chamo Ana, lembre disso"}]})
    shown = "".join(event["text"] for event in got if event["type"] == "delta")
    assert "LEMBRAR" not in shown and got[-1]["text"] == "Prazer, Ana! Vou lembrar."
    assert store.stored == ["A pessoa se chama Ana"]
    system = seen[0][0]["content"]
    assert "- O dono se chama Eduardo" in system and "[[LEMBRAR" in system


def test_forget_and_no_database(monkeypatch):
    store = FakeMemory([])
    api, _ = build(monkeypatch, ["Pronto, esqueci.", "[[ESQUECER: preço antigo]]"], store)
    got = events(api, {"messages": [{"role": "user", "content": "esquece o preço antigo"}]})
    assert got[-1]["text"] == "Pronto, esqueci." and store.forgotten == ["preço antigo"] and store.stored == []
    api, seen = build(monkeypatch, ["Ok.", "[[LEMBRAR: algo]]"], None)
    got = events(api, {"messages": [{"role": "user", "content": "lembra disso"}]})
    assert got[-1]["text"] == "Ok." and "[[LEMBRAR" not in seen[0][0]["content"]
