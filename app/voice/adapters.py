from __future__ import annotations

import importlib.util
import platform
import re
import threading
from dataclasses import dataclass

from app.voice.models import Transcript, VoiceAvailability


@dataclass(slots=True)
class EnergyVadState:
    threshold: float
    silence_blocks: int
    min_speech_blocks: int = 1
    speaking: bool = False
    quiet_blocks: int = 0
    speech_blocks: int = 0

    def feed(self, energy: float) -> str:
        if not self.speaking and energy >= self.threshold:
            self.speaking = True
            self.speech_blocks = 1
            return "start"
        if not self.speaking:
            return "waiting"
        if energy < self.threshold:
            self.quiet_blocks += 1
        else:
            self.quiet_blocks = 0
            self.speech_blocks += 1
        can_end = self.speech_blocks >= self.min_speech_blocks
        return "end" if can_end and self.quiet_blocks >= self.silence_blocks else "speech"


class SoundDeviceMicrophone:
    """Captures model-ready 16 kHz mono float audio when sounddevice is installed."""

    def __init__(self, sample_rate: int = 16_000) -> None:
        self.sample_rate = sample_rate
        self._cancelled = threading.Event()

    def availability(self) -> VoiceAvailability:
        if importlib.util.find_spec("sounddevice") is None:
            return VoiceAvailability(False, "dependência opcional sounddevice não instalada")
        try:
            import sounddevice as sd

            device = sd.query_devices(kind="input")
            return VoiceAvailability(bool(device), "microfone de entrada disponível")
        except Exception as exc:  # noqa: BLE001 - backend errors vary by PortAudio host API
            return VoiceAvailability(False, f"microfone indisponível: {exc}")

    def record(self, seconds: float) -> object:
        if seconds <= 0:
            raise ValueError("seconds deve ser positivo")
        status = self.availability()
        if not status.available:
            raise RuntimeError(status.detail)
        import sounddevice as sd

        self._cancelled.clear()
        frames = int(seconds * self.sample_rate)
        audio = sd.rec(frames, samplerate=self.sample_rate, channels=1, dtype="float32")
        sd.wait()
        if self._cancelled.is_set():
            raise RuntimeError("captura cancelada")
        return audio.reshape(-1)

    def record_until_silence(
        self,
        *,
        max_seconds: float = 15.0,
        start_timeout: float = 8.0,
        silence_seconds: float = 0.8,
        energy_threshold: float = 0.015,
        min_speech_seconds: float = 0.25,
        adaptive_noise: bool = True,
        block_ms: int = 30,
    ) -> object:
        """Local energy VAD with bounded start wait, end-of-turn silence and duration."""
        status = self.availability()
        if not status.available:
            raise RuntimeError(status.detail)
        import numpy as np
        import sounddevice as sd

        self._cancelled.clear()
        block_frames = max(1, int(self.sample_rate * block_ms / 1_000))
        start_blocks = max(1, int(start_timeout * 1_000 / block_ms))
        silence_blocks = max(1, int(silence_seconds * 1_000 / block_ms))
        min_speech_blocks = max(1, int(min_speech_seconds * 1_000 / block_ms))
        max_blocks = max(1, int(max_seconds * 1_000 / block_ms))
        preroll: list[object] = []
        captured: list[object] = []
        vad = EnergyVadState(energy_threshold, silence_blocks, min_speech_blocks)
        noise_samples: list[float] = []
        with sd.InputStream(
            samplerate=self.sample_rate, channels=1, dtype="float32", blocksize=block_frames
        ) as stream:
            for index in range(max_blocks):
                if self._cancelled.is_set():
                    raise RuntimeError("captura cancelada")
                block, _overflowed = stream.read(block_frames)
                mono = block.reshape(-1).copy()
                energy = float(np.sqrt(np.mean(np.square(mono))))
                if adaptive_noise and not vad.speaking:
                    noise_samples.append(energy)
                    del noise_samples[:-20]
                    # Keep the configured threshold as a floor.  A local noise
                    # estimate avoids both premature starts and cloud audio.
                    if len(noise_samples) >= 5:
                        noise_floor = sorted(noise_samples)[len(noise_samples) // 2]
                        vad.threshold = max(energy_threshold, noise_floor * 2.5)
                state = vad.feed(energy)
                if state in {"waiting", "start"} and not captured:
                    preroll.append(mono)
                    del preroll[:-10]
                    if state == "start":
                        captured.extend(preroll)
                    elif index >= start_blocks:
                        raise TimeoutError("nenhuma fala detectada")
                    continue
                captured.append(mono)
                if state == "end":
                    break
        if not captured:
            raise TimeoutError("nenhuma fala detectada")
        return np.concatenate(captured)

    def cancel(self) -> None:
        self._cancelled.set()
        if importlib.util.find_spec("sounddevice") is not None:
            try:
                import sounddevice as sd

                sd.stop()
            except Exception:  # noqa: BLE001 - cancellation must remain best effort
                return


class FasterWhisperRecognizer:
    """Lazy local STT; no model is downloaded until transcription is requested."""

    def __init__(self, model: str = "base", language: str | None = "pt") -> None:
        self.model_name = model
        self.language = language
        self._model = None

    def availability(self) -> VoiceAvailability:
        installed = importlib.util.find_spec("faster_whisper") is not None
        detail = "faster-whisper instalado; o modelo pode exigir download inicial" if installed else (
            "dependência opcional faster-whisper não instalada"
        )
        return VoiceAvailability(installed, detail)

    def transcribe(self, audio: object) -> Transcript:
        status = self.availability()
        if not status.available:
            raise RuntimeError(status.detail)
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self.model_name, device="auto", compute_type="default")
        segments, info = self._model.transcribe(
            audio, language=self.language, vad_filter=True, word_timestamps=True
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return Transcript(text=text, language=getattr(info, "language", self.language))


class SapiSynthesizer:
    """Windows SAPI TTS with asynchronous speech and purge-based cancellation."""

    ASYNC = 1
    PURGE_BEFORE_SPEAK = 2

    def __init__(
        self,
        rate: int = -1,
        volume: int = 92,
        voice_name: str | None = None,
        *,
        language: str = "pt-BR",
        max_chunk_chars: int = 280,
    ) -> None:
        self.rate = max(-10, min(10, rate))
        self.volume = max(0, min(100, volume))
        self.voice_name = voice_name.strip() if voice_name else None
        self.language = language
        self.max_chunk_chars = max(80, min(800, max_chunk_chars))
        self._voice = None
        self.selected_voice_name: str | None = None

    def availability(self) -> VoiceAvailability:
        available = platform.system() == "Windows" and importlib.util.find_spec("win32com") is not None
        return VoiceAvailability(available, "Windows SAPI disponível" if available else "Windows SAPI indisponível")

    def _get_voice(self):
        if self._voice is None:
            if not self.availability().available:
                raise RuntimeError("Windows SAPI indisponível")
            import win32com.client

            self._voice = win32com.client.Dispatch("SAPI.SpVoice")
            self._voice.Rate = self.rate
            self._voice.Volume = self.volume
            candidate = self._select_voice(self._voice.GetVoices())
            if candidate is not None:
                self._voice.Voice = candidate
                self.selected_voice_name = candidate.GetDescription()
        return self._voice

    def _select_voice(self, voices):
        """Prefer an explicit name, then an installed Brazilian Portuguese voice."""
        candidates = [voices.Item(index) for index in range(voices.Count)]
        if self.voice_name:
            wanted = self.voice_name.casefold()
            return next(
                (item for item in candidates if wanted in item.GetDescription().casefold()),
                None,
            )
        locale_markers = ("pt-br", "pt_br", "portuguese (brazil)", "português (brasil)")

        def score(item) -> tuple[int, int]:
            description = item.GetDescription().casefold()
            try:
                language = str(item.GetAttribute("Language")).casefold()
            except Exception:  # noqa: BLE001 - token attributes vary between SAPI voices
                language = ""
            combined = f"{description} {language}"
            locale_score = 2 if "416" in language else int(any(x in combined for x in locale_markers))
            # Known Windows neural/natural labels win when already installed.
            natural_score = int(any(x in combined for x in ("natural", "neural", "online")))
            return locale_score, natural_score

        return max(candidates, key=score, default=None) if candidates else None

    def available_voices(self) -> tuple[str, ...]:
        """Return installed SAPI voice descriptions without retaining audio."""
        voice = self._get_voice()
        voices = voice.GetVoices()
        return tuple(voices.Item(index).GetDescription() for index in range(voices.Count))

    def speak(self, text: str) -> None:
        prepared = normalize_text_for_speech(text)
        if prepared:
            voice = self._get_voice()
            for chunk in chunk_text_for_speech(prepared, self.max_chunk_chars):
                # Consecutive asynchronous SAPI calls are queued in order. Splitting
                # only at linguistic boundaries avoids clipped words and UI stalls.
                voice.Speak(chunk, self.ASYNC)

    def cancel(self) -> None:
        if self._voice is not None:
            self._voice.Speak("", self.ASYNC | self.PURGE_BEFORE_SPEAK)

    def wait_until_done(self, timeout_ms: int = 30_000) -> bool:
        return bool(self._voice is None or self._voice.WaitUntilDone(timeout_ms))


def normalize_text_for_speech(text: str) -> str:
    """Remove visual markup and repair spacing without changing factual content."""
    value = text.strip()
    value = re.sub(r"```(?:\w+)?\s*(.*?)```", r"\1", value, flags=re.DOTALL)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"(?m)^\s{0,3}(?:#{1,6}|[-*+] |\d+[.)] )\s*", "", value)
    value = re.sub(r"[*_~]", "", value)
    value = re.sub(r"\s*\n+\s*", ". ", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\.{2,}", ".", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    return value.strip(" .") + ("." if value.strip(" .") else "")


def chunk_text_for_speech(text: str, max_chars: int = 280) -> tuple[str, ...]:
    """Split on sentence/clause/word boundaries; never cut a word."""
    if not text:
        return ()
    sentences = re.split(r"(?<=[.!?;:])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        units = [sentence]
        if len(sentence) > max_chars:
            units = re.split(r"(?<=,)\s+", sentence)
        for unit in units:
            words = unit.split()
            while words:
                candidate = f"{current} {' '.join(words)}".strip()
                if len(candidate) <= max_chars:
                    current = candidate
                    break
                available = max_chars - len(current) - bool(current)
                take = 0
                length = 0
                for word in words:
                    extra = len(word) + bool(length)
                    if take and length + extra > available:
                        break
                    length += extra
                    take += 1
                if take == 0:
                    if current:
                        chunks.append(current)
                        current = ""
                        continue
                    take = 1  # a single unusually long token remains intact
                piece = " ".join(words[:take])
                current = f"{current} {piece}".strip()
                words = words[take:]
                if words:
                    chunks.append(current)
                    current = ""
    if current:
        chunks.append(current)
    return tuple(chunks)
