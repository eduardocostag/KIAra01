"""Render composition.html frame by frame (deterministic clock) and mux the narration.

Usage: python render.py [--seconds N] [--output out/kiara-demo.mp4]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=0, help="Render only the first N seconds (test).")
    parser.add_argument("--output", default="out/kiara-demo.mp4")
    args = parser.parse_args()
    timeline = json.loads((ROOT / "assets" / "timeline.json").read_text(encoding="utf-8"))
    fps, duration = timeline["fps"], timeline["duration"]
    if args.seconds:
        duration = min(duration, args.seconds)
    frames = int(duration * fps)
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg não encontrado no PATH.")
    encoder = subprocess.Popen([
        ffmpeg, "-y", "-v", "error",
        "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
        "-i", str(ROOT / "assets" / "narration.wav"),
        "-map", "0:v", "-map", "1:a", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "192k", str(output),
    ], stdin=subprocess.PIPE)
    started = time.monotonic()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.goto((ROOT / "composition.html").as_uri())
        page.wait_for_function("typeof window.renderAt === 'function'")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(500)
        for frame in range(frames):
            page.evaluate(f"renderAt({frame / fps:.4f})")
            encoder.stdin.write(page.screenshot(type="jpeg", quality=94))
            if frame % (fps * 10) == 0:
                elapsed = time.monotonic() - started
                print(f"{frame / fps:6.1f}s / {duration:.1f}s  ({elapsed:.0f}s de renderização)", flush=True)
        browser.close()
    encoder.stdin.close()
    if encoder.wait() != 0:
        raise SystemExit("ffmpeg falhou ao codificar o vídeo.")
    print(f"pronto: {output} ({frames} quadros em {time.monotonic() - started:.0f}s)")


if __name__ == "__main__":
    main()
