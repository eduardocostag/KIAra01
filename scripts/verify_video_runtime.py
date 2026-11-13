"""Generate a one-second local media smoke test, without using an LLM or customer data."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.video_studio.engine import find_ffmpeg, narrate, render


def main() -> None:
    project = ROOT / "evidence/kiara-stability/media-smoke"
    project.mkdir(parents=True, exist_ok=True)
    (project / "script.json").write_text(json.dumps({"scenes": [
        {"id": "smoke", "layout": "orb", "text": "Olá, eu sou a Kiara."},
    ]}, ensure_ascii=False), encoding="utf-8")
    timeline = narrate(project)
    video = render(project, quality="720p", workers=1, seconds=1)
    decoded = subprocess.run([find_ffmpeg(), "-v", "error", "-i", str(video), "-f", "null", "-"],
                             capture_output=True, timeout=60, check=False)
    result = {"narration_seconds": timeline["duration"], "video_bytes": video.stat().st_size,
              "decode_success": decoded.returncode == 0, "video": str(video.relative_to(ROOT))}
    (project.parent / "media-runtime.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    if decoded.returncode:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
