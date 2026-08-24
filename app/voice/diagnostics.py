from __future__ import annotations

from app.voice.adapters import FasterWhisperRecognizer, SapiSynthesizer, SoundDeviceMicrophone


def voice_diagnostics() -> dict[str, dict[str, object]]:
    components = {
        "microphone": SoundDeviceMicrophone(),
        "stt": FasterWhisperRecognizer(),
        "tts": SapiSynthesizer(),
    }
    result = {
        name: {"available": result.available, "detail": result.detail}
        for name, component in components.items()
        if (result := component.availability())
    }
    result["features"] = {
        "available": result["microphone"]["available"] and result["stt"]["available"],
        "detail": "VAD local, wake word por transcrição e modo conversa disponíveis quando captura/STT estão ativos",
    }
    return result
