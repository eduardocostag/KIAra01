from __future__ import annotations

import asyncio
import importlib.util
import logging
import platform
import re
import tempfile
import threading
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from app.voice.models import Transcript, VoiceAvailability

logger = logging.getLogger(__name__)


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
        detail = (
            "faster-whisper instalado; o modelo pode exigir download inicial"
            if installed
            else ("dependência opcional faster-whisper não instalada")
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
        collected = list(segments)
        text = " ".join(segment.text.strip() for segment in collected).strip()
        first_word = next(
            (
                word
                for segment in collected
                for word in (getattr(segment, "words", None) or ())
                if str(getattr(word, "word", "")).strip()
            ),
            None,
        )
        probability = getattr(first_word, "probability", None)
        confidence = float(probability) if isinstance(probability, int | float) else None
        return Transcript(
            text=text,
            language=getattr(info, "language", self.language),
            confidence=confidence,
        )


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
        available = (
            platform.system() == "Windows" and importlib.util.find_spec("win32com") is not None
        )
        return VoiceAvailability(
            available, "Windows SAPI disponível" if available else "Windows SAPI indisponível"
        )

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
            locale_score = (
                2 if "416" in language else int(any(x in combined for x in locale_markers))
            )
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


class EdgeNeuralSynthesizer:
    """Natural online pt-BR speech with cancellable playback and local fallback."""

    def __init__(
        self,
        *,
        voice: str = "pt-BR-ThalitaMultilingualNeural",
        rate: str = "-4%",
        pitch: str = "-2Hz",
        timeout_seconds: float = 18,
        fallback=None,
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.timeout_seconds = max(3.0, min(60.0, timeout_seconds))
        self.fallback = fallback
        self.language = "pt-BR"
        self.volume = 100
        self.selected_voice_name = voice
        self._cancelled = threading.Event()
        self._finished = threading.Event()
        self._finished.set()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._async_task: asyncio.Task | None = None

    def availability(self) -> VoiceAvailability:
        available = all(
            importlib.util.find_spec(name) is not None
            for name in ("edge_tts", "sounddevice", "soundfile")
        )
        detail = (
            f"Edge Neural disponível ({self.voice})"
            if available
            else "Edge Neural indisponível; Kokoro local será usado"
        )
        return VoiceAvailability(available, detail)

    def speak(self, text: str) -> None:
        prepared = normalize_text_for_speech(text)
        if not prepared:
            return
        self.cancel()
        self._cancelled.clear()
        self._finished.clear()
        self._thread = threading.Thread(
            target=self._download_and_play, args=(prepared,), daemon=True
        )
        self._thread.start()

    def _download_and_play(self, text: str) -> None:
        audio_path: Path | None = None
        try:
            if not self.availability().available:
                raise RuntimeError("Edge Neural indisponível")
            import edge_tts
            import sounddevice as sd
            import soundfile as sf

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as target:
                audio_path = Path(target.name)
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            communication = edge_tts.Communicate(
                text, self.voice, rate=self.rate, pitch=self.pitch
            )
            self._async_task = self._loop.create_task(communication.save(str(audio_path)))
            self._loop.run_until_complete(
                asyncio.wait_for(self._async_task, timeout=self.timeout_seconds)
            )
            if not self._cancelled.is_set():
                samples, sample_rate = sf.read(audio_path, dtype="float32")
                sd.play(samples, samplerate=sample_rate, blocking=True)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Edge Neural falhou; usando fallback local")
            if self.fallback is not None and not self._cancelled.is_set():
                self.fallback.speak(text)
                self.fallback.wait_until_done()
        finally:
            if self._loop is not None:
                self._loop.close()
            self._loop = None
            self._async_task = None
            if audio_path is not None:
                audio_path.unlink(missing_ok=True)
            self._finished.set()

    def cancel(self) -> None:
        self._cancelled.set()
        loop, task = self._loop, self._async_task
        if loop is not None and task is not None and loop.is_running():
            loop.call_soon_threadsafe(task.cancel)
        with suppress(Exception):
            if importlib.util.find_spec("sounddevice") is not None:
                import sounddevice as sd

                sd.stop()
        if self.fallback is not None:
            self.fallback.cancel()
        self._finished.set()

    def wait_until_done(self, timeout_ms: int = 30_000) -> bool:
        return self._finished.wait(max(0, timeout_ms) / 1_000)


class KokoroSynthesizer:
    """Local neural pt-BR speech with cancellable playback and SAPI fallback."""

    SYSTEM_ESPEAK = Path(r"C:\Program Files\eSpeak NG\libespeak-ng.dll")

    def __init__(
        self,
        *,
        voice: str = "pf_dora",
        speed: float = 0.94,
        device: str = "cpu",
        fallback: SapiSynthesizer | None = None,
        max_chunk_chars: int = 280,
    ) -> None:
        self.voice = voice
        self.speed = max(0.7, min(1.3, speed))
        self.device = device
        self.fallback = fallback
        self.max_chunk_chars = max(80, min(500, max_chunk_chars))
        self.language = "pt-BR"
        self.rate = fallback.rate if fallback is not None else -1
        self.volume = fallback.volume if fallback is not None else 92
        self.selected_voice_name = voice
        self._pipeline = None
        self._cancelled = threading.Event()
        self._finished = threading.Event()
        self._finished.set()
        self._thread: threading.Thread | None = None

    def availability(self) -> VoiceAvailability:
        dependencies = all(
            importlib.util.find_spec(name) is not None for name in ("kokoro", "sounddevice")
        )
        espeak = self.SYSTEM_ESPEAK.is_file()
        available = dependencies and espeak
        detail = (
            f"Kokoro local disponível ({self.voice}, {self.language})"
            if available
            else "Kokoro indisponível; Windows SAPI será usado"
        )
        return VoiceAvailability(available, detail)

    def _get_pipeline(self):
        if self._pipeline is None:
            # misaki's portable Windows loader can retain its build-machine data
            # path. The installed eSpeak NG library discovers its own data safely.
            from kokoro import KPipeline
            from phonemizer.backend.espeak.wrapper import EspeakWrapper

            EspeakWrapper.set_library(str(self.SYSTEM_ESPEAK))
            EspeakWrapper.set_data_path(None)
            self._pipeline = KPipeline(
                lang_code="p", repo_id="hexgrad/Kokoro-82M", device=self.device
            )
        return self._pipeline

    def speak(self, text: str) -> None:
        prepared = normalize_text_for_speech(text)
        if not prepared:
            return
        self.cancel()
        self._cancelled.clear()
        self._finished.clear()
        self._thread = threading.Thread(
            target=self._synthesize_and_play, args=(prepared,), daemon=True
        )
        self._thread.start()

    def _synthesize_and_play(self, text: str) -> None:
        try:
            if not self.availability().available:
                raise RuntimeError("Kokoro local indisponível")
            import sounddevice as sd

            pipeline = self._get_pipeline()
            for chunk in chunk_text_for_speech(text, self.max_chunk_chars):
                if self._cancelled.is_set():
                    break
                for result in pipeline(chunk, voice=self.voice, speed=self.speed):
                    if self._cancelled.is_set():
                        break
                    audio = result.audio
                    if audio is None:
                        continue
                    samples = audio.detach().cpu().numpy()
                    sd.play(samples, samplerate=24_000, blocking=True)
        except Exception:
            logger.exception("Kokoro falhou; usando Windows SAPI")
            if self.fallback is not None and not self._cancelled.is_set():
                self.fallback.speak(text)
                self.fallback.wait_until_done()
        finally:
            self._finished.set()

    def cancel(self) -> None:
        self._cancelled.set()
        with suppress(Exception):
            if importlib.util.find_spec("sounddevice") is not None:
                import sounddevice as sd

                sd.stop()
        if self.fallback is not None:
            self.fallback.cancel()
        self._finished.set()

    def wait_until_done(self, timeout_ms: int = 30_000) -> bool:
        return self._finished.wait(max(0, timeout_ms) / 1_000)


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
