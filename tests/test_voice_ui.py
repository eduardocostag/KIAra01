from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from app.ui.desktop import VoiceWorker
from app.voice.models import Transcript


class FakeVoice:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.spoken: list[str] = []

    def listen(self, seconds, on_state):
        on_state("Ouvindo…")
        on_state("Transcrevendo…")
        if self.fail:
            raise RuntimeError("sem microfone")
        return Transcript("teste por voz", "pt")

    def speak(self, text):
        self.spoken.append(text)

    def cancel(self):
        return None


def test_voice_worker_emits_lifecycle_and_transcript():
    worker = VoiceWorker(FakeVoice(), 3)
    states, transcripts = [], []
    worker.state_changed.connect(states.append)
    worker.transcript_ready.connect(transcripts.append)
    worker.listen()
    assert states == ["Ouvindo…", "Transcrevendo…", "Pronta"]
    assert transcripts == ["teste por voz"]


def test_voice_worker_recovers_from_optional_backend_failure():
    worker = VoiceWorker(FakeVoice(fail=True), 3)
    errors, states = [], []
    worker.failed.connect(errors.append)
    worker.state_changed.connect(states.append)
    worker.listen()
    assert errors == ["sem microfone"]
    assert states[-1] == "Pronta"


def test_voice_worker_reports_speaking_state():
    voice = FakeVoice()
    worker = VoiceWorker(voice, 3)
    states = []
    worker.state_changed.connect(states.append)
    worker.speak("Olá")
    assert voice.spoken == ["Olá"]
    assert states == ["Falando…", "Pronta"]
