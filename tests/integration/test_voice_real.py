from __future__ import annotations

import os

import pytest

from app.voice.adapters import SoundDeviceMicrophone


@pytest.mark.skipif(
    os.environ.get("KIARA_RUN_VOICE_INTEGRATION") != "1",
    reason="set KIARA_RUN_VOICE_INTEGRATION=1 with a real microphone to run",
)
def test_real_microphone_vad_captures_a_spoken_turn():
    microphone = SoundDeviceMicrophone()
    availability = microphone.availability()
    if not availability.available:
        pytest.skip(availability.detail)
    audio = microphone.record_until_silence(max_seconds=8, start_timeout=5)
    assert len(audio) > 0
