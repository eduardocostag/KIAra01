"""Narration (Edge TTS), word timings, pronunciation check and the composition timeline.

Outputs (assets/):
  audio/<scene>.mp3 + <scene>.words.json   clip and spoken-word timings
  narration.wav                             all clips joined (final audio track)
  timeline.json / timeline.js               scenes with absolute cue times + voice envelope
Use --check to transcribe each clip back with Whisper and flag words that do not match.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import shutil
import struct
import subprocess
import unicodedata
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
FPS = 30
RATE = 24_000


def ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise SystemExit("ffmpeg não encontrado no PATH.")
    return path


def norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return re.sub(r"[^a-z0-9 ]", "", "".join(c for c in text if unicodedata.category(c) != "Mn"))


def decode(path: Path) -> bytes:
    return subprocess.run([ffmpeg(), "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
                          check=True, capture_output=True).stdout


async def synthesize(text: str, voice: str, rate: str, target: Path) -> list[dict]:
    """Save the clip and return [{text, start, end}] for each spoken word (seconds)."""
    words, audio = [], bytearray()
    async for chunk in edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary").stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            start = chunk["offset"] / 10_000_000
            words.append({"text": chunk["text"], "start": round(start, 3), "end": round(start + chunk["duration"] / 10_000_000, 3)})
    target.write_bytes(bytes(audio))
    return words


def cue_time(words: list[dict], cue: str, after: float = 0.0) -> float | None:
    key = norm(cue).split()[0]
    for word in words:
        if word["start"] >= after and norm(word["text"]).startswith(key):
            return word["start"]
    return None


def check(scenes: list[dict]) -> None:
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    for scene in scenes:
        clip = ASSETS / "audio" / f"{scene['id']}.mp3"
        segments, _ = model.transcribe(str(clip), language="pt", beam_size=5)
        heard = " ".join(segment.text.strip() for segment in segments)
        expected = set(norm(scene["text"]).split())
        missing = [word for word in norm(heard).split() if word not in expected and len(word) > 3]
        print(f"\n[{scene['id']}] ouvido: {heard}")
        if missing:
            print(f"  ⚠ palavras diferentes do roteiro: {', '.join(missing)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Transcribe clips back with Whisper to spot mispronunciations.")
    args = parser.parse_args()
    script = json.loads((ROOT / "script.json").read_text(encoding="utf-8"))
    (ASSETS / "audio").mkdir(parents=True, exist_ok=True)
    gap = bytes(int(script["gap_seconds"] * RATE) * 2)
    pcm = bytearray(bytes(int(1.2 * RATE) * 2))  # the avatar wakes up before speaking
    scenes = []
    for scene in script["scenes"]:
        clip = ASSETS / "audio" / f"{scene['id']}.mp3"
        timings = ASSETS / "audio" / f"{scene['id']}.words.json"
        if not clip.exists() or not timings.exists():
            words = asyncio.run(synthesize(scene.get("speech", scene["text"]), script["voice"], script["rate"], clip))
            timings.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
        words = json.loads(timings.read_text(encoding="utf-8"))
        samples = decode(clip)
        start = len(pcm) / 2 / RATE
        pcm.extend(samples)
        end = len(pcm) / 2 / RATE
        pcm.extend(gap)

        def at(cue: str | None, fallback: float) -> float:
            found = cue_time(words, cue) if cue else None
            if cue and found is None:
                print(f"  ⚠ [{scene['id']}] palavra-gatilho não encontrada: {cue}")
            return round(start + (found if found is not None else fallback), 3)

        resolved = {k: v for k, v in scene.items() if k not in {"text", "speech"}}
        resolved.update(caption=scene["text"], start=round(start, 3), end=round(end, 3))
        for key in ("cards", "words", "spots"):
            if key in scene:
                resolved[key] = [{**item, "at": at(item.get("cue"), 1.0 + index * 1.5)} for index, item in enumerate(scene[key])]
        if "shots" in scene:
            resolved["shots"] = [{**item, "at": at(item.get("cue"), 0.0) if item.get("cue") else round(start, 3)} for item in scene["shots"]]
        # Caption words with absolute times, used to highlight what is being said.
        resolved["spoken"] = [{"text": word["text"], "at": round(start + word["start"], 3)} for word in words]
        scenes.append(resolved)
        print(f"{scene['id']:12s} {end - start:5.1f}s")
    pcm.extend(bytes(int(2.4 * RATE) * 2))

    wav = ASSETS / "narration.wav"
    data = bytes(pcm)
    with wav.open("wb") as handle:
        handle.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, RATE, RATE * 2, 2, 16) + b"data" + struct.pack("<I", len(data)) + data)

    values = struct.unpack(f"<{len(pcm) // 2}h", data)
    step = RATE // FPS
    raw = [math.sqrt(sum(v * v for v in values[i:i + step]) / max(1, len(values[i:i + step]))) for i in range(0, len(values), step)]
    peak = sorted(raw)[int(len(raw) * 0.98)] or 1
    envelope, previous = [], 0.0
    for value in raw:
        level = min(1.0, value / peak)
        previous = level if level > previous else previous * 0.8 + level * 0.2
        envelope.append(round(previous, 3))
    duration = len(pcm) / 2 / RATE
    timeline = json.dumps({"fps": FPS, "duration": round(duration, 3), "scenes": scenes, "envelope": envelope}, ensure_ascii=False)
    (ASSETS / "timeline.json").write_text(timeline, encoding="utf-8")
    # The composition is opened from disk (file://), where fetch() is blocked: ship it as a script.
    (ASSETS / "timeline.js").write_text(f"window.TIMELINE = {timeline};\n", encoding="utf-8")
    print(f"total {duration:.1f}s, {len(envelope)} quadros")
    if args.check:
        check(script["scenes"])


if __name__ == "__main__":
    main()
