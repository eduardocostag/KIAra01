from pathlib import Path

from app.bootstrap import build_voice_service
from app.config import Settings
from app.voice.adapters import EnergyVadState
from app.voice.models import Transcript
from app.voice.service import VoiceService


class FakeMicrophone:
    def __init__(self):
        self.cancelled = False

    def record(self, seconds):
        return [seconds]

    def cancel(self):
        self.cancelled = True


class FakeRecognizer:
    def transcribe(self, audio):
        return Transcript(f"audio:{audio[0]}", "pt")


class FakeSynthesizer:
    def __init__(self):
        self.spoken = []
        self.cancel_count = 0

    def speak(self, text):
        self.spoken.append(text)

    def cancel(self):
        self.cancel_count += 1


def test_listen_interrupts_tts_before_capture():
    tts = FakeSynthesizer()
    service = VoiceService(FakeMicrophone(), FakeRecognizer(), tts)
    assert service.listen(2).text == "audio:2"
    assert tts.cancel_count == 1


def test_listen_reports_capture_and_transcription_states():
    states = []
    service = VoiceService(FakeMicrophone(), FakeRecognizer(), FakeSynthesizer())
    service.listen(1, states.append)
    assert states == ["Ouvindo…", "Transcrevendo…"]


def test_cancel_stops_input_and_output():
    mic, tts = FakeMicrophone(), FakeSynthesizer()
    service = VoiceService(mic, FakeRecognizer(), tts)
    service.cancel()
    assert mic.cancelled
    assert tts.cancel_count == 1


def test_shutdown_prevents_monitor_restart():
    service = VoiceService(FakeMicrophone(), FakeRecognizer(), FakeSynthesizer())
    service.shutdown()
    assert not service.is_listening
    try:
        service.listen(1)
    except RuntimeError as exc:
        assert "encerrado" in str(exc)
    else:
        raise AssertionError("listen deveria rejeitar serviço encerrado")


def test_listening_state_is_cleared_after_recognizer_error():
    class BrokenRecognizer:
        def transcribe(self, audio):
            raise RuntimeError("falha de STT")

    service = VoiceService(FakeMicrophone(), BrokenRecognizer(), FakeSynthesizer())
    try:
        service.listen(1)
    except RuntimeError:
        pass
    assert not service.is_listening


def test_speak_delegates_without_hardware():
    tts = FakeSynthesizer()
    VoiceService(FakeMicrophone(), FakeRecognizer(), tts).speak("Olá")
    assert tts.spoken == ["Olá"]


def test_voice_factory_is_disabled_by_default():
    settings = Settings({"voice": {"enabled": False}}, Path.cwd())
    assert build_voice_service(settings) is None


def test_voice_factory_does_not_initialize_optional_backends():
    settings = Settings({"voice": {"enabled": True}}, Path.cwd())
    service = build_voice_service(settings)
    assert service is not None
    assert service.recognizer._model is None


def test_voice_factory_supports_opt_in_always_on_wake_monitor():
    settings = Settings(
        {"voice": {"enabled": True, "always_listen_for_wake_word": True}}, Path.cwd()
    )
    service = build_voice_service(settings)
    assert service is not None
    assert service.always_listen_for_wake_word
    assert service.require_wake_word


def test_always_on_monitor_requires_wake_word_for_every_turn():
    class SequenceRecognizer:
        def __init__(self):
            self.transcripts = iter(
                (
                    Transcript("Kiara, abra o bloco de notas", "pt"),
                    Transcript("apague todos os arquivos", "pt"),
                )
            )

        def transcribe(self, audio):
            return next(self.transcripts)

    service = VoiceService(
        FakeMicrophone(),
        SequenceRecognizer(),
        FakeSynthesizer(),
        always_listen_for_wake_word=True,
    )
    assert service.listen(1).text == "abra o bloco de notas"
    assert service.conversation_mode is False
    assert service.listen(1).text == ""


def test_wake_word_is_consumed_and_activates_conversation():
    class WakeRecognizer:
        def transcribe(self, audio):
            return Transcript("Kiara, abra o bloco de notas", "pt")

    service = VoiceService(
        FakeMicrophone(), WakeRecognizer(), FakeSynthesizer(), require_wake_word=True
    )
    result = service.listen(1)
    assert result.text == "abra o bloco de notas"
    assert service.conversation_mode


def test_required_wake_word_rejects_unactivated_turn():
    class NoWakeRecognizer:
        def transcribe(self, audio):
            return Transcript("abra o bloco de notas", "pt")

    service = VoiceService(
        FakeMicrophone(), NoWakeRecognizer(), FakeSynthesizer(), require_wake_word=True
    )
    assert service.listen(1).text == ""


def test_conversation_mode_allows_followup_without_wake_word():
    class FollowupRecognizer:
        def transcribe(self, audio):
            return Transcript("como resolvo", "pt")

    service = VoiceService(
        FakeMicrophone(), FollowupRecognizer(), FakeSynthesizer(), require_wake_word=True
    )
    service.start_conversation()
    assert service.listen(1).text == "como resolvo"


def test_energy_vad_detects_start_and_end_without_hardware():
    vad = EnergyVadState(threshold=0.1, silence_blocks=2)
    assert vad.feed(0.01) == "waiting"
    assert vad.feed(0.2) == "start"
    assert vad.feed(0.3) == "speech"
    assert vad.feed(0.01) == "speech"
    assert vad.feed(0.01) == "end"


def test_vad_ignores_short_impulse_before_endpointing():
    vad = EnergyVadState(threshold=0.1, silence_blocks=2, min_speech_blocks=3)
    assert vad.feed(0.2) == "start"
    assert vad.feed(0.01) == "speech"
    assert vad.feed(0.01) == "speech"
    assert vad.feed(0.3) == "speech"
    assert vad.feed(0.3) == "speech"
    assert vad.feed(0.01) == "speech"
    assert vad.feed(0.01) == "end"


def test_incidental_wake_word_mention_does_not_activate():
    class IncidentalRecognizer:
        def transcribe(self, audio):
            return Transcript("eu falei da Kiara ontem", "pt")

    service = VoiceService(
        FakeMicrophone(), IncidentalRecognizer(), FakeSynthesizer(), require_wake_word=True
    )
    assert service.listen(1).text == ""


def test_protected_conversation_requires_address_each_turn():
    class FollowupRecognizer:
        def transcribe(self, audio):
            return Transcript("apague os arquivos", "pt")

    service = VoiceService(
        FakeMicrophone(),
        FollowupRecognizer(),
        FakeSynthesizer(),
        require_wake_word=True,
        conversation_requires_wake_word=True,
    )
    service.start_conversation()
    assert service.listen(1).text == ""
