import asyncio
import base64
import io
import json

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from kiara_api import chat, chat_search
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError

ASK = [{"role": "user", "content": "Vai chover amanhã em Porto Alegre?"}]


def build(monkeypatch, scripts, *, completions=None, search_results=None):
    """scripts: per model, the chunks it streams (an Exception item makes it fail at that point)."""
    monkeypatch.setenv("KIARA_CHAT_API_BASE_URL", "")
    monkeypatch.setenv("KIARA_CHAT_API_KEY", "")
    monkeypatch.setenv("KIARA_CHAT_MODEL", "claude/claude-sonnet-5-5")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_URL", "https://kiara-debian.example.ts.net")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_TOKEN", "gw")
    monkeypatch.setenv("KIARA_CHAT_FALLBACKS", "b/second,c/third")
    monkeypatch.setenv("EXA_API_KEY", "exa")
    seen = {"conversations": [], "searches": []}
    rounds = {}

    async def streamer(base, key, model, conversation, max_tokens, timeout):
        seen["conversations"].append((model, conversation))
        script = scripts.get(model, [RuntimeError("down")])
        if script and isinstance(script[0], list):  # one script per call of the same model
            index = rounds.get(model, 0)
            rounds[model] = index + 1
            script = script[min(index, len(script) - 1)]
        for piece in script:
            if isinstance(piece, Exception):
                raise piece
            yield piece

    class Provider:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def _complete(self, messages):
            seen["conversations"].append((self.kwargs["model"], messages))
            replies = completions or ["ok"]
            return replies.pop(0) if len(replies) > 1 else replies[0]

    async def search(query):
        seen["searches"].append(query)
        return search_results if search_results is not None else [
            {"title": "Previsão Porto Alegre amanhã", "url": "https://www.climatempo.com.br/poa", "date": "2026-11-15",
             "text": "Domingo 15/11: chuva à tarde, 19° a 28°."}]

    monkeypatch.setattr(chat_search, "web_search", search)
    app = FastAPI()
    app.include_router(chat.create_chat_router(Provider, streamer=streamer))

    @app.exception_handler(ApiError)
    async def error(_request, exc):
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status_code)

    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", "org", "m", "owner", "req", email="admin@kiara.local")
    return TestClient(app), seen


def events(api, body):
    with api.stream("POST", "/v1/chat/stream", json=body) as response:
        assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
        return [json.loads(line[5:]) for line in response.iter_lines() if line.startswith("data:")]


def test_answer_arrives_in_pieces(monkeypatch):
    api, _ = build(monkeypatch, {"claude/claude-sonnet-5-5": ["Fotossíntese ", "é o processo ", "das plantas."]})
    got = events(api, {"messages": [{"role": "user", "content": "O que é fotossíntese?"}]})
    assert [e["text"] for e in got if e["type"] == "delta"] == ["Fotossíntese ", "é o processo ", "das plantas."]
    assert got[-1] == {"type": "done", "text": "Fotossíntese é o processo das plantas.", "model": "claude/claude-sonnet-5-5"}


def test_failing_providers_fall_back_and_partial_text_is_reset(monkeypatch):
    api, _ = build(monkeypatch, {
        "claude/claude-sonnet-5-5": [RuntimeError("429 quota")],             # fails before any token: silent
        "b/second": ["Começo da resp", RuntimeError("connection reset")],   # fails mid-answer: reset
        "c/third": ["Resposta completa."],
    })
    got = events(api, {"messages": ASK})
    kinds = [e["type"] for e in got]
    assert kinds == ["delta", "reset", "delta", "done"]
    assert got[-1]["text"] == "Resposta completa." and got[-1]["model"] == "c/third"


def test_markers_are_never_shown_while_streaming(monkeypatch):
    api, _ = build(monkeypatch, {"claude/claude-sonnet-5-5": ["<think>hmm</think>Claro! ", "Olha só:\n[", "[IMAGEM: um farol]]"]})
    monkeypatch.setattr(chat, "image_available", lambda: False)
    got = events(api, {"messages": [{"role": "user", "content": "faz um farol"}]})
    shown = "".join(e["text"] for e in got if e["type"] == "delta")
    assert "[" not in shown and "think" not in shown and shown.startswith("Claro!")


def test_search_round_trip_with_sources(monkeypatch):
    api, seen = build(monkeypatch, {"claude/claude-sonnet-5-5": [
        ["[[PESQUISAR: previsão do tempo Porto Alegre amanhã]]"],
        ["Segundo o Climatempo, ", "deve chover à tarde."],
    ]})
    got = events(api, {"messages": ASK})
    assert seen["searches"] == ["previsão do tempo Porto Alegre amanhã"]
    assert {"type": "status", "text": "Pesquisando na internet…"} in got
    done = got[-1]
    assert done["text"] == "Segundo o Climatempo, deve chover à tarde."
    assert done["sources"] == [{"title": "Previsão Porto Alegre amanhã", "url": "https://www.climatempo.com.br/poa", "site": "climatempo.com.br"}]
    second_system = seen["conversations"][-1][1][0]["content"]
    assert "Resultados de uma pesquisa na internet" in second_system and "chuva à tarde" in second_system
    assert chat_search.SEARCH_STYLE in seen["conversations"][0][1][0]["content"]


def test_messages_endpoint_also_searches(monkeypatch):
    api, seen = build(monkeypatch, {}, completions=["[[PESQUISAR: dólar hoje]]", "O dólar fechou em R$ 5,65 (Banco Central)."])
    body = api.post("/v1/chat/messages", json={"messages": [{"role": "user", "content": "quanto está o dólar?"}]}).json()
    assert seen["searches"] == ["dólar hoje"] and body["text"].startswith("O dólar fechou") and body["sources"]


def test_search_needs_no_paid_key_and_can_be_turned_off(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("KIARA_WEB_SEARCH", raising=False)
    assert chat.NO_INTERNET not in chat.site_context() and chat_search.SEARCH_STYLE in chat.site_context()
    monkeypatch.setenv("KIARA_WEB_SEARCH", "off")
    assert chat.site_context() == chat.SITE_CONTEXT and chat.NO_INTERNET in chat.SITE_CONTEXT


def test_free_search_reads_result_pages_and_quotes(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("KIARA_WEB_SEARCH", raising=False)
    monkeypatch.setattr(chat_search, "_duckduckgo", lambda q: [{"title": "Wise", "url": "https://wise.com/dolar", "date": "", "text": "Conversor"}])
    monkeypatch.setattr(chat_search, "_bing", lambda q: [{"title": "UOL", "url": "https://economia.uol.com.br/c", "date": "", "text": "Câmbio"},
                                                         {"title": "Wise", "url": "https://wise.com/dolar/", "date": "", "text": "dup"}])
    monkeypatch.setattr(chat_search, "_read_page", lambda url: "Menu\nA cotação do dólar hoje é 5,88 reais no câmbio comercial.\nRodapé")
    monkeypatch.setattr(chat_search, "_quotes", lambda codes: {"title": "Cotação", "url": "https://economia.awesomeapi.com.br/",
                                                               "date": "", "text": f"{codes[0]} R$ 5,88"})
    results = asyncio.run(chat_search.web_search("cotação do dólar hoje"))
    assert [chat_search._host(r["url"]) for r in results] == ["economia.awesomeapi.com.br", "wise.com", "economia.uol.com.br"]
    assert results[0]["text"] == "USD R$ 5,88" and "5,88 reais" in results[1]["text"]
    assert chat_search._bing_target("https://www.bing.com/ck/a?!&&p=x&u=a1aHR0cHM6Ly9nMS5nbG9iby5jb20v&ntb=1") == "https://g1.globo.com/"


def _pdf(text):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 20 200 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return base64.b64encode(out.getvalue()).decode()


def test_photos_and_pdfs_reach_the_model(monkeypatch):
    api, seen = build(monkeypatch, {"claude/claude-sonnet-5-5": ["Vi a foto e o contrato."]})
    jpeg = base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 100).decode()
    body = {"messages": [{"role": "user", "content": "O que acha?"}], "attachments": [
        {"name": "foto.jpg", "mime": "image/jpeg", "data_base64": jpeg},
        {"name": "contrato.pdf", "mime": "application/pdf", "data_base64": _pdf("Prazo de 12 meses")}]}
    got = events(api, body)
    assert got[-1]["text"] == "Vi a foto e o contrato."
    last = seen["conversations"][0][1][-1]["content"]
    assert last[0]["type"] == "text" and "Prazo de 12 meses" in last[0]["text"] and "[Imagem anexada: foto.jpg]" in last[0]["text"]
    assert last[1] == {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + jpeg}}


def test_fake_files_are_refused(monkeypatch):
    api, _ = build(monkeypatch, {})
    fake = base64.b64encode(b"MZ executable pretending").decode()
    response = api.post("/v1/chat/stream", json={"messages": ASK, "attachments": [
        {"name": "x.jpg", "mime": "image/jpeg", "data_base64": fake}]})
    assert response.status_code == 422 and response.json()["error"]["code"] == "attachment_invalid"


def test_voice_stream_voices_the_first_phrase_on_the_server(monkeypatch):
    monkeypatch.delenv("KIARA_VOICE_DIRECT_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    spoken = []

    async def fake_speak(text):
        spoken.append(text)
        return b"mp3-bytes", "francisca"

    monkeypatch.setattr(chat, "speak", fake_speak)
    monkeypatch.setattr(chat, "speech_available", lambda: True)
    api, _ = build(monkeypatch, {chat.DEFAULT_VOICE_MODEL: ["Lead frio ainda não ", "conhece sua empresa, ", "enquanto o quente já ", "conversou com você."]})
    got = events(api, {"messages": [{"role": "user", "content": "Lead frio e quente?"}], "voice": True})
    kinds = [e["type"] for e in got]
    # The app hears about the phrase before the text that completes it, then gets its audio in the same stream.
    pending = kinds.index("speech_pending")
    assert kinds[pending + 1] == "delta" and got[pending + 1]["text"] == "conhece sua empresa, "
    assert got[pending]["chars"] == len("Lead frio ainda não conhece sua empresa, ")
    speech = next(e for e in got if e["type"] == "speech")
    assert speech["chars"] == got[pending]["chars"] and base64.b64decode(speech["audio_base64"]) == b"mp3-bytes"
    assert spoken == ["Lead frio ainda não conhece sua empresa, "] and kinds[-1] == "done"
    # Written chat: nothing of this.
    got = events(api, {"messages": [{"role": "user", "content": "Lead frio e quente?"}]})
    assert not [e for e in got if e["type"] in ("speech_pending", "speech")]
