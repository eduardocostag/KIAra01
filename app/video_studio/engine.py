"""Kiara Video Studio: presentation videos with the Kiara avatar narrating.

Pipeline (one folder per project):
  script.json          scenes, narration text and on-screen cues (see SKILL.md)
  shots/<name>.png     1920x1080 screenshots used by "shot" scenes
  build/               audio clips, narration.wav, timeline.js and composition.html
  out/video.mp4        final H.264 + AAC video

narrate() turns the script into speech (Edge TTS) with word timings and resolves every cue
to an absolute time; render() draws the composition frame by frame in headless Chromium
(several workers in parallel) and encodes it with ffmpeg.
"""
from __future__ import annotations

import asyncio
import glob
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
import unicodedata
from collections.abc import Callable
from pathlib import Path

from app.voice.kiara_style import PRONUNCIATION, RATE as SPEECH_RATE, VOICE, spoken  # noqa: F401 - re-exported

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).with_name("template.html")
LIBRARY_SHOTS = ROOT / "app" / "resources" / "video_studio" / "shots"
FPS = 30
RATE = 24_000
LAYOUTS = {"hello", "orb", "shot", "custom", "control", "outro"}
ALIASES = {"modules": "custom", "highlight": "control", "intro": "orb", "screen": "shot", "greeting": "hello", "closing": "outro"}
DEFAULT_VOICE = VOICE
QUALITIES = {"1080p": 1.0, "720p": 2 / 3}
Progress = Callable[[str, float, str], None]


class VideoError(RuntimeError):
    pass


def find_ffmpeg() -> str:
    candidates = [os.environ.get("KIARA_FFMPEG", ""), shutil.which("ffmpeg") or ""]
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        candidates += sorted(glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "*FFmpeg*", "**", "bin", "ffmpeg.exe"), recursive=True))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        bundled = get_ffmpeg_exe()
        if Path(bundled).is_file():
            return bundled
    except (ImportError, RuntimeError, OSError):
        pass
    raise VideoError("ffmpeg não encontrado. Instale com: winget install Gyan.FFmpeg")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return re.sub(r"[^a-z0-9 ]", "", "".join(c for c in text if unicodedata.category(c) != "Mn"))


def _clean(value, limit: int, name: str, *, optional: bool = False) -> str:
    if value is None and optional:
        return ""
    if not isinstance(value, str) or (not optional and not value.strip()) or len(value) > limit:
        raise VideoError(f"Campo inválido no roteiro: {name}.")
    return " ".join(value.split())


def _items(scene: dict, key: str, limit: int, sid: str) -> list[dict]:
    raw = scene.get(key) or []
    if not isinstance(raw, list):
        raise VideoError(f"[{sid}] {key} deve ser uma lista.")
    result = []
    for item in raw[:limit]:
        if isinstance(item, str):
            item = {"text": item}
        if not isinstance(item, dict):
            raise VideoError(f"[{sid}] item inválido em {key}.")
        entry = {"text": _clean(item.get("text"), 60, f"{sid}.{key}.text")}
        if item.get("cue"):
            entry["cue"] = _clean(item["cue"], 40, f"{sid}.{key}.cue")
        result.append(entry)
    return result


def validate_script(script: dict, shots_dir: Path | None = None) -> dict:
    """Normalize a script (from a person or a model) and reject anything unsafe or broken."""
    if not isinstance(script, dict) or not isinstance(script.get("scenes"), list):
        raise VideoError("O roteiro precisa de uma lista de cenas.")
    voice = script.get("voice") or DEFAULT_VOICE
    if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}-[A-Za-z]+Neural", voice):
        raise VideoError("Voz inválida.")
    rate = script.get("rate") or SPEECH_RATE
    if not re.fullmatch(r"[+-]\d{1,2}%", rate):
        raise VideoError("Velocidade da voz inválida (use, por exemplo, +2%).")
    gap = float(script.get("gap_seconds", 0.45))
    meta_in = script.get("meta") or {}
    audience = [_clean(name, 30, "meta.audience") for name in (meta_in.get("audience") or [])[:3]]
    meta = {
        "brand": _clean(meta_in.get("brand") or "KIARA", 30, "meta.brand"),
        "audience": audience,
        "cta": _clean(meta_in.get("cta"), 80, "meta.cta", optional=True),
        "app_label": _clean(meta_in.get("app_label") or "app.kiara", 40, "meta.app_label"),
        "for_label": _clean(meta_in.get("for_label") or "Apresentação para", 40, "meta.for_label"),
        "pronunciation": {str(k)[:40]: str(v)[:60] for k, v in (meta_in.get("pronunciation") or {}).items()} if isinstance(meta_in.get("pronunciation"), dict) else {},
    }
    scenes, seen = [], set()
    if not 1 <= len(script["scenes"]) <= 16:
        raise VideoError("Use entre 1 e 16 cenas.")
    for index, raw in enumerate(script["scenes"]):
        if not isinstance(raw, dict):
            raise VideoError("Cena inválida.")
        sid = re.sub(r"[^a-z0-9-]", "-", str(raw.get("id") or f"cena-{index + 1}").lower())[:30].strip("-") or f"cena-{index + 1}"
        while sid in seen:
            sid += "-b"
        seen.add(sid)
        layout = ALIASES.get(raw.get("layout"), raw.get("layout"))
        if layout not in LAYOUTS:
            raise VideoError(f"[{sid}] layout desconhecido: {raw.get('layout')}.")
        accent = raw.get("accent") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(raw.get("accent"))) else "#a78bfa"
        scene = {"id": sid, "layout": layout, "accent": accent, "text": _clean(raw.get("text"), 420, f"{sid}.text")}
        speech = _clean(raw.get("speech"), 480, f"{sid}.speech", optional=True)
        scene["speech"] = speech or spoken(scene["text"], meta["pronunciation"])
        for key, limit in (("kicker", 40), ("title", 70), ("greeting", 30), ("pill", 60), ("new_tile", 30)):
            if key in raw and raw[key] is not None:
                scene[key] = _clean(raw[key], limit, f"{sid}.{key}", optional=True)
        scene["cards"] = _items(raw, "cards", 4, sid)
        scene["words"] = _items(raw, "words", 3, sid)
        if raw.get("cardsSide") == "left":
            scene["cardsSide"] = "left"
        if layout == "custom" and raw.get("tiles"):
            scene["tiles"] = [{"text": _clean(tile.get("text") if isinstance(tile, dict) else tile, 24, f"{sid}.tiles"),
                               "color": tile.get("color") if isinstance(tile, dict) and re.fullmatch(r"#[0-9a-fA-F]{6}", str(tile.get("color"))) else accent}
                              for tile in raw["tiles"][:6]]
        if layout == "shot":
            shots = raw.get("shots") or []
            if not isinstance(shots, list) or not 1 <= len(shots) <= 3:
                raise VideoError(f"[{sid}] cenas de tela precisam de 1 a 3 telas.")
            scene["kicker"] = scene.get("kicker") or scene.get("title") or ""
            scene["shots"] = []
            for shot in shots:
                if isinstance(shot, str):
                    shot = {"shot": shot}
                name = str(shot.get("shot", ""))
                if not re.fullmatch(r"[a-z0-9-]{1,60}", name):
                    raise VideoError(f"[{sid}] nome de tela inválido: {name}.")
                if shots_dir is not None and not (shots_dir / f"{name}.png").is_file():
                    raise VideoError(f"[{sid}] tela não encontrada: {name}.png.")
                focus = shot.get("focus") or [960, 540, 1.08]
                fx, fy, zoom = (float(v) for v in focus[:3])
                entry = {"shot": name, "focus": [min(1920, max(0, fx)), min(1080, max(0, fy)), min(1.4, max(1, zoom))]}
                if shot.get("cue"):
                    entry["cue"] = _clean(shot["cue"], 40, f"{sid}.shots.cue")
                scene["shots"].append(entry)
            scene["spots"] = [{"cue": _clean(s.get("cue"), 40, f"{sid}.spots.cue", optional=True),
                               "x": min(1920, max(0, float(s.get("x", 960)))), "y": min(1080, max(0, float(s.get("y", 540))))}
                              for s in (raw.get("spots") or [])[:3] if isinstance(s, dict)]
        scenes.append(scene)
    return {"voice": voice, "rate": rate, "gap_seconds": min(1.5, max(0.1, gap)), "meta": meta, "scenes": scenes}


# ---------------------------------------------------------------- narration
async def _synthesize(text: str, voice: str, rate: str, target: Path) -> list[dict]:
    import edge_tts

    words, audio = [], bytearray()
    async for chunk in edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary").stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            start = chunk["offset"] / 10_000_000
            words.append({"text": chunk["text"], "start": round(start, 3), "end": round(start + chunk["duration"] / 10_000_000, 3)})
    if not audio:
        raise VideoError("A voz não retornou áudio. Verifique a internet.")
    target.write_bytes(bytes(audio))
    return words


def _decode(ffmpeg: str, path: Path) -> bytes:
    return subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
                          check=True, capture_output=True).stdout


def _cue_time(words: list[dict], cue: str) -> float | None:
    key = (norm(cue).split() or [""])[0]
    for word in words:
        if key and norm(word["text"]).startswith(key):
            return word["start"]
    return None


def narrate(project: Path, *, progress: Progress | None = None) -> dict:
    """Synthesize each scene, build narration.wav and timeline.js. Clips are cached by text."""
    script = validate_script(json.loads((project / "script.json").read_text(encoding="utf-8")), project / "shots")
    ffmpeg = find_ffmpeg()
    build = project / "build"
    (build / "audio").mkdir(parents=True, exist_ok=True)
    gap = bytes(int(script["gap_seconds"] * RATE) * 2)
    pcm = bytearray(bytes(int(1.2 * RATE) * 2))  # the avatar wakes up before speaking
    scenes, warnings = [], []
    for number, scene in enumerate(script["scenes"]):
        if progress:
            progress("narration", number / len(script["scenes"]), f"Gravando a fala da cena {number + 1} de {len(script['scenes'])}")
        clip, timings = build / "audio" / f"{scene['id']}.mp3", build / "audio" / f"{scene['id']}.words.json"
        signature = json.dumps([scene["speech"], script["voice"], script["rate"]], ensure_ascii=False)
        cached = timings.is_file() and clip.is_file() and json.loads(timings.read_text(encoding="utf-8")).get("signature") == signature
        if not cached:
            words = asyncio.run(_synthesize(scene["speech"], script["voice"], script["rate"], clip))
            timings.write_text(json.dumps({"signature": signature, "words": words}, ensure_ascii=False), encoding="utf-8")
        words = json.loads(timings.read_text(encoding="utf-8"))["words"]
        start = len(pcm) / 2 / RATE
        pcm.extend(_decode(ffmpeg, clip))
        end = len(pcm) / 2 / RATE
        pcm.extend(gap)

        def at(cue: str | None, fallback: float, sid=scene["id"], words=words, start=start) -> float:
            found = _cue_time(words, cue) if cue else None
            if cue and found is None:
                warnings.append(f"[{sid}] palavra-gatilho não encontrada na fala: {cue}")
            return round(start + (found if found is not None else fallback), 3)

        resolved = {k: v for k, v in scene.items() if k not in {"text", "speech"}}
        resolved.update(caption=scene["text"], start=round(start, 3), end=round(end, 3))
        for key in ("cards", "words", "spots"):
            if key in scene:
                resolved[key] = [{**item, "at": at(item.get("cue"), 1.0 + index * 1.5)} for index, item in enumerate(scene[key])]
        if "shots" in scene:
            resolved["shots"] = [{**item, "at": at(item.get("cue"), 0.0) if item.get("cue") else round(start, 3)} for item in scene["shots"]]
        scenes.append(resolved)
    pcm.extend(bytes(int(2.4 * RATE) * 2))
    data = bytes(pcm)
    with (build / "narration.wav").open("wb") as handle:
        handle.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, RATE, RATE * 2, 2, 16)
                     + b"data" + struct.pack("<I", len(data)) + data)
    values = struct.unpack(f"<{len(pcm) // 2}h", data)
    step = RATE // FPS
    raw = [math.sqrt(sum(v * v for v in values[i:i + step]) / max(1, len(values[i:i + step]))) for i in range(0, len(values), step)]
    peak = sorted(raw)[int(len(raw) * 0.98)] or 1
    envelope, previous = [], 0.0
    for value in raw:
        level = min(1.0, value / peak)
        previous = level if level > previous else previous * 0.8 + level * 0.2
        envelope.append(round(previous, 3))
    timeline = {"fps": FPS, "duration": round(len(pcm) / 2 / RATE, 3), "meta": script["meta"], "scenes": scenes, "envelope": envelope}
    text = json.dumps(timeline, ensure_ascii=False)
    (build / "timeline.json").write_text(text, encoding="utf-8")
    # The composition opens from disk (file://), where fetch() is blocked: ship the data as a script.
    safe = text.replace("</", "<\\/")
    (build / "timeline.js").write_text("window.TIMELINE = " + safe + ";\n", encoding="utf-8")
    shutil.copyfile(TEMPLATE, build / "composition.html")
    timeline["warnings"] = warnings
    return timeline


def check_pronunciation(project: Path) -> list[str]:
    """Transcribe each clip back (faster-whisper) and list words that differ from the script."""
    from faster_whisper import WhisperModel

    script = validate_script(json.loads((project / "script.json").read_text(encoding="utf-8")))
    model = WhisperModel("base", device="cpu", compute_type="int8")
    issues = []
    for scene in script["scenes"]:
        segments, _ = model.transcribe(str(project / "build" / "audio" / f"{scene['id']}.mp3"), language="pt", beam_size=5)
        heard = " ".join(segment.text.strip() for segment in segments)
        expected = set(norm(scene["text"] + " " + scene["speech"]).split())
        odd = [word for word in norm(heard).split() if word not in expected and len(word) > 3]
        if odd:
            issues.append(f"[{scene['id']}] ouvido: \"{heard}\" — confira: {', '.join(odd)}")
    return issues


# ---------------------------------------------------------------- rendering
def render_range(build: Path, first: int, last: int, scale: float, output: Path) -> None:
    """Worker: render frames [first, last) to a video-only segment. Prints one line per 30 frames."""
    from playwright.sync_api import sync_playwright

    timeline = json.loads((build / "timeline.json").read_text(encoding="utf-8"))
    fps = timeline["fps"]
    encoder = subprocess.Popen([
        find_ffmpeg(), "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(fps), str(output),
    ], stdin=subprocess.PIPE)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=scale)
        page.goto((build / "composition.html").as_uri())
        page.wait_for_function("typeof window.renderAt === 'function'")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(400)
        for frame in range(first, last):
            page.evaluate(f"renderAt({frame / fps:.4f})")
            encoder.stdin.write(page.screenshot(type="jpeg", quality=92))
            if (frame - first) % fps == fps - 1:
                print("frames", fps, flush=True)
        browser.close()
    encoder.stdin.close()
    if encoder.wait() != 0:
        raise SystemExit(2)


def render(project: Path, output: Path | None = None, *, quality: str = "1080p", workers: int = 0,
           seconds: float = 0, progress: Progress | None = None) -> Path:
    """Render build/composition.html in parallel workers, then join segments and add the narration."""
    if quality not in QUALITIES:
        raise VideoError("Qualidade deve ser 1080p ou 720p.")
    build = project / "build"
    timeline = json.loads((build / "timeline.json").read_text(encoding="utf-8"))
    fps, duration = timeline["fps"], timeline["duration"]
    if seconds:
        duration = min(duration, seconds)
    frames = int(duration * fps)
    workers = workers or max(1, min(6, (os.cpu_count() or 2) // 3))
    output = output or project / "out" / "video.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    segments = build / "segments"
    shutil.rmtree(segments, ignore_errors=True)
    segments.mkdir()
    bounds = [round(frames * n / workers) for n in range(workers + 1)]
    done, lock, started = [0], threading.Lock(), time.monotonic()
    processes = []
    for n in range(workers):
        command = [sys.executable, "-I", "-m", "app.video_studio", "worker", str(build), str(bounds[n]), str(bounds[n + 1]),
                   str(QUALITIES[quality]), str(segments / f"{n:02d}.mp4")]
        processes.append(subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))

    def follow(process):
        for line in process.stdout:
            if line.startswith("frames"):
                with lock:
                    done[0] += int(line.split()[1])
                    if progress:
                        elapsed = time.monotonic() - started
                        left = elapsed / max(1, done[0]) * (frames - done[0])
                        progress("render", done[0] / frames, f"Renderizando: {done[0] * 100 // frames}% (cerca de {math.ceil(left / 60)} min restantes)")

    readers = [threading.Thread(target=follow, args=(p,), daemon=True) for p in processes]
    for reader in readers:
        reader.start()
    failed = [p.wait() for p in processes]
    for reader in readers:
        reader.join(timeout=5)
    if any(failed):
        errors = " ".join((p.stderr.read() or "")[-400:] for p in processes)
        raise VideoError(f"A renderização falhou. {errors.strip()}")
    (segments / "list.txt").write_text("".join(f"file '{n:02d}.mp4'\n" for n in range(workers)), encoding="utf-8")
    if progress:
        progress("encode", 0.98, "Juntando vídeo e narração")
    subprocess.run([
        find_ffmpeg(), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(segments / "list.txt"),
        "-i", str(build / "narration.wav"), "-map", "0:v", "-map", "1:a", "-t", f"{duration:.3f}",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output),
    ], check=True)
    shutil.rmtree(segments, ignore_errors=True)
    return output


def preview_frames(project: Path, moments: list[float], target: Path) -> list[Path]:
    """Save JPEG stills of the composition at the given seconds (for a quick visual check)."""
    from playwright.sync_api import sync_playwright

    target.mkdir(parents=True, exist_ok=True)
    paths = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto((project / "build" / "composition.html").as_uri())
        page.wait_for_function("typeof window.renderAt === 'function'")
        for moment in moments:
            page.evaluate(f"renderAt({moment:.3f})")
            path = target / f"frame-{moment:06.1f}.jpg"
            page.screenshot(path=str(path), type="jpeg", quality=80)
            paths.append(path)
        browser.close()
    return paths
