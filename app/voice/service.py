from __future__ import annotations

import re
import threading
from collections.abc import Callable

from app.voice.models import Transcript
from app.voice.ports import Microphone, SpeechRecognizer, SpeechSynthesizer


class VoiceService:
    """Coordinates push-to-talk and TTS; listening interrupts current speech (barge-in)."""

    def __init__(
        self,
        microphone: Microphone,
        recognizer: SpeechRecognizer,
        synthesizer: SpeechSynthesizer,
        *,
        wake_word: str = "Kiara",
        require_wake_word: bool = False,
        vad_enabled: bool = True,
        continuous_conversation: bool = False,
        always_listen_for_wake_word: bool = False,
        conversation_requires_wake_word: bool = False,
    ) -> None:
        self.microphone = microphone
        self.recognizer = recognizer
        self.synthesizer = synthesizer
        self.wake_word = wake_word.strip()
        # A background microphone is only safe as a wake-word monitor.  Do not
        # permit a contradictory configuration to turn ambient speech into a
        # command stream.
        self.require_wake_word = require_wake_word or always_listen_for_wake_word
        self.vad_enabled = vad_enabled
        self.conversation_mode = continuous_conversation
        self.always_listen_for_wake_word = always_listen_for_wake_word
        self.conversation_requires_wake_word = conversation_requires_wake_word
        self._lock = threading.RLock()
        self._state_lock = threading.Lock()
        self._listening = False
        self._closed = False

    def listen(
        self, seconds: float = 5.0, on_state: Callable[[str], None] | None = None
    ) -> Transcript:
        with self._state_lock:
            if self._closed:
                raise RuntimeError("serviço de voz encerrado")
            if self._listening:
                raise RuntimeError("captura de voz já está em andamento")
            self._listening = True
        try:
            with self._lock:
                self.synthesizer.cancel()
                if on_state:
                    on_state("Ouvindo…")
                vad_capture = getattr(self.microphone, "record_until_silence", None)
                audio = (
                    vad_capture(max_seconds=seconds)
                    if self.vad_enabled and vad_capture is not None
                    else self.microphone.record(seconds)
                )
                if on_state:
                    on_state("Transcrevendo…")
                return self._apply_wake_word(self.recognizer.transcribe(audio))
        finally:
            with self._state_lock:
                self._listening = False

    def speak(self, text: str) -> None:
        with self._lock:
            self.synthesizer.speak(text)

    def cancel(self) -> None:
        self.microphone.cancel()
        self.synthesizer.cancel()

    @property
    def is_listening(self) -> bool:
        with self._state_lock:
            return self._listening

    def shutdown(self) -> None:
        """Stop input/output and prevent queued monitor cycles from restarting."""
        with self._state_lock:
            self._closed = True
        self.cancel()

    def start_conversation(self) -> None:
        self.conversation_mode = True

    def stop_conversation(self) -> None:
        self.conversation_mode = False

    def wait_until_spoken(self, timeout_ms: int = 30_000) -> bool:
        wait = getattr(self.synthesizer, "wait_until_done", None)
        return bool(wait(timeout_ms)) if wait is not None else True

    def _apply_wake_word(self, transcript: Transcript) -> Transcript:
        text = transcript.text.strip()
        if not self.wake_word:
            return transcript
        prefix = self.wake_word.casefold()
        normalized = text.casefold()
        # The address must be the first spoken token.  This avoids activating
        # on incidental mentions such as "falei da Kiara ontem".
        match = re.match(rf"^{re.escape(prefix)}(?:\s|[,.:;!?-]|$)+", normalized)
        activated = bool(match)
        if activated:
            command = text[len(self.wake_word) :].lstrip(" ,.:;-")
            # Always-listen remains a sequence of isolated wake-word turns.
            # Persistent follow-ups require the separately visible conversation
            # mode instead of being enabled implicitly by one activation.
            if not self.always_listen_for_wake_word:
                self.conversation_mode = True
            return Transcript(command, transcript.language)
        wake_required_now = self.require_wake_word and (
            not self.conversation_mode or self.conversation_requires_wake_word
        )
        if wake_required_now:
            return Transcript("", transcript.language)
        return transcript
