"""Generate the narration (Edge TTS, pt-BR) and the timeline used by the composition.

Outputs (assets/):
  audio/<scene>.mp3      one clip per scene
  narration.wav          all clips joined with gaps (final audio track)
  timeline.json          scene start/end times + 30 fps voice envelope for the orb
"""
from __future__ import annotations

import asyncio
import json
import math
import shutil
import struct
import subprocess
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
FPS = 30
RATE = 24_000  # mono PCM used for the joined track and the envelope


def ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise SystemExit("ffmpeg não encontrado no PATH.")
    return path


def decode(path: Path) -> bytes:
    """Decode any audio file to mono 16-bit PCM at RATE."""
    return subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
                          check=True, capture_output=True).stdout


async def synthesize(text: str, voice: str, rate: str, target: Path) -> None:
    await edge_tts.Communicate(text, voice, rate=rate).save(str(target))


def main() -> None:
    script = json.loads((ROOT / "script.json").read_text(encoding="utf-8"))
    (ASSETS / "audio").mkdir(parents=True, exist_ok=True)
    gap = bytes(int(script["gap_seconds"] * RATE) * 2)
    lead_in = bytes(int(0.8 * RATE) * 2)  # orb appears before Kiara starts talking
    pcm = bytearray(lead_in)
    scenes = []
    for scene in script["scenes"]:
        clip = ASSETS / "audio" / f"{scene['id']}.mp3"
        if not clip.exists():
            asyncio.run(synthesize(scene["text"], script["voice"], script["rate"], clip))
        samples = decode(clip)
        start = len(pcm) / 2 / RATE
        pcm.extend(samples)
        end = len(pcm) / 2 / RATE
        pcm.extend(gap)
        scenes.append({**{k: v for k, v in scene.items() if k != "text"}, "caption": scene["text"], "start": round(start, 3), "end": round(end, 3)})
        print(f"{scene['id']:16s} {end - start:5.1f}s")
    pcm.extend(bytes(int(1.6 * RATE) * 2))  # tail for the closing card

    wav = ASSETS / "narration.wav"
    with wav.open("wb") as handle:
        data = bytes(pcm)
        handle.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, RATE, RATE * 2, 2, 16) + b"data" + struct.pack("<I", len(data)) + data)

    # Envelope: RMS per video frame, normalized and lightly smoothed.
    values = struct.unpack(f"<{len(pcm) // 2}h", bytes(pcm))
    step = RATE // FPS
    raw = [math.sqrt(sum(v * v for v in values[i:i + step]) / max(1, len(values[i:i + step]))) for i in range(0, len(values), step)]
    peak = sorted(raw)[int(len(raw) * 0.98)] or 1
    envelope, previous = [], 0.0
    for value in raw:
        level = min(1.0, value / peak)
        previous = level if level > previous else previous * 0.82 + level * 0.18
        envelope.append(round(previous, 3))
    duration = len(pcm) / 2 / RATE
    timeline = json.dumps({"fps": FPS, "duration": round(duration, 3), "scenes": scenes, "envelope": envelope}, ensure_ascii=False)
    (ASSETS / "timeline.json").write_text(timeline, encoding="utf-8")
    # The composition is opened from disk (file://), where fetch() is blocked: ship it as a script.
    (ASSETS / "timeline.js").write_text(f"window.TIMELINE = {timeline};\n", encoding="utf-8")
    print(f"total {duration:.1f}s, {len(envelope)} frames")


if __name__ == "__main__":
    main()
