import asyncio
import time
from datetime import UTC, datetime, timedelta

from kiara_api import transcription, whatsapp_server
from kiara_api.whatsapp_server import WhatsAppServerService, conversation_messages


class Client:
    def __init__(self):
        self.asked = []

    async def media(self, session_id, chat_id, message_id, *, limit):
        self.asked.append(message_id)
        return (b"OggS...", "audio/ogg; codecs=opus") if message_id != "broken" else None


def test_new_voice_notes_become_text_and_old_ones_stay(monkeypatch):
    now = datetime.now(UTC)
    rows = [
        {"waMessageId": "old", "direction": "incoming", "type": "ptt", "body": "", "timestamp": (now - timedelta(days=2)).timestamp()},
        {"waMessageId": "new", "direction": "incoming", "type": "ptt", "body": "", "timestamp": now.timestamp()},
        {"waMessageId": "broken", "direction": "incoming", "type": "audio", "body": "", "timestamp": now.timestamp() + 1},
        {"waMessageId": "mine", "direction": "outgoing", "type": "ptt", "body": "", "timestamp": now.timestamp() + 2},
        {"waMessageId": "photo", "direction": "incoming", "type": "image", "body": "", "timestamp": now.timestamp() + 3},
    ]
    messages = conversation_messages(rows)
    calls = []

    async def fake(raw, mime="audio/ogg", *, timeout=40):
        calls.append((raw, mime))
        return "quero um orçamento para o site"

    monkeypatch.setattr(transcription, "transcribe", fake)
    client = Client()
    service = WhatsAppServerService.__new__(WhatsAppServerService)
    left = asyncio.run(service._transcribe_new(client, "s", "5551@c.us", rows, messages, now - timedelta(hours=1),
                                               time.monotonic() + 60, 3))
    texts = {item["external_id"]: item["text"] for item in messages}
    assert texts["new"] == "[áudio] quero um orçamento para o site"
    assert texts["old"] == texts["broken"] == texts["mine"] == "[áudio]" and texts["photo"] == "[imagem]"
    assert client.asked == ["new", "broken"] and left == 1 and calls == [(b"OggS...", "audio/ogg; codecs=opus")]


def test_no_gateway_means_no_transcription(monkeypatch):
    monkeypatch.setattr(transcription, "gateway_configuration", lambda: ("", ""))
    assert asyncio.run(transcription.transcribe(b"x" * 100)) == ""


def test_multipart_carries_model_language_and_file():
    body, kind = transcription._multipart({"model": "m", "language": "pt"}, "file", "audio.ogg", "audio/ogg", b"RAW")
    assert kind.startswith("multipart/form-data; boundary=")
    assert b'name="language"\r\n\r\npt' in body and b'filename="audio.ogg"' in body and b"RAW" in body
    assert whatsapp_server.AUDIO_KINDS == {"audio", "ptt"}
