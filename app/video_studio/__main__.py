"""Command line for Kiara Video Studio.

  python -m app.video_studio narrate <projeto> [--check]
  python -m app.video_studio render  <projeto> [--quality 1080p|720p] [--workers N] [--seconds N] [--output arquivo.mp4]
  python -m app.video_studio preview <projeto> <segundos> [<segundos> ...]
  python -m app.video_studio make    <projeto> ...        narrate + render
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.video_studio.engine import check_pronunciation, narrate, preview_frames, render, render_range


def log(stage: str, value: float, message: str) -> None:
    print(f"[{stage}] {message}", flush=True)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        _, _, build, first, last, scale, output = sys.argv
        render_range(Path(build), int(first), int(last), float(scale), Path(output))
        return
    parser = argparse.ArgumentParser(prog="python -m app.video_studio")
    parser.add_argument("command", choices=["narrate", "render", "preview", "make"])
    parser.add_argument("project", type=Path)
    parser.add_argument("moments", nargs="*", type=float)
    parser.add_argument("--check", action="store_true", help="Confere a pronúncia transcrevendo a fala (faster-whisper).")
    parser.add_argument("--quality", default="1080p", choices=["1080p", "720p"])
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    if args.command in {"narrate", "make"}:
        timeline = narrate(project, progress=log)
        for warning in timeline["warnings"]:
            print("  ! ", warning)
        print(f"narração: {timeline['duration']:.1f}s")
        if args.check:
            for issue in check_pronunciation(project):
                print("  ! ", issue)
    if args.command == "preview":
        for path in preview_frames(project, args.moments or [2.0], project / "build" / "preview"):
            print(path)
    if args.command in {"render", "make"}:
        output = render(project, args.output, quality=args.quality, workers=args.workers, seconds=args.seconds, progress=log)
        print(f"pronto: {output}")


if __name__ == "__main__":
    main()
