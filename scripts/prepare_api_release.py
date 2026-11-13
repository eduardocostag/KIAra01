"""Package the API and shared Kiara runtime without local data or credentials."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SKIP = frozenset({"__pycache__", ".git", "node_modules", ".venv", "tests"})


def prepare_release(output: Path | None = None) -> dict[str, object]:
    release_root = (ROOT / ".release").resolve()
    destination = (output or release_root / f"kiara-api-{uuid4().hex[:12]}").resolve()
    if not destination.is_relative_to(release_root) or destination == release_root:
        raise ValueError("A saída deve ser uma subpasta de .release no workspace.")
    destination.mkdir(parents=True, exist_ok=False)
    copied = []
    sources = [
        (ROOT / "services/api/kiara_api", "kiara_api"),
        (ROOT / "services/api/api", "api"),
        (ROOT / "services/api/migrations", "migrations"),
        (ROOT / "app", "app"),
    ]
    for source, prefix in sources:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if (not path.is_file() or path.is_symlink() or SKIP.intersection(relative.parts)
                    or any(part.startswith(".env") for part in relative.parts)):
                continue
            landing_resource = prefix == "app" and relative.parts[:3] == (
                "resources", "operational_skills", "kiara-web-studio",
            )
            landing_asset = landing_resource and path.suffix.lower() in {
                ".html", ".css", ".js", ".mjs", ".yaml", ".yml", ".txt", ".ps1",
                ".webp", ".avif", ".png", ".jpg", ".jpeg", ".svg", ".mp4", ".webm",
            }
            if path.suffix not in {".py", ".json", ".md", ".sql"} and path.name != "LICENSE" and not landing_asset:
                continue
            target = destination / prefix / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            copied.append(target.relative_to(destination).as_posix())
    for name in ("requirements.txt", "vercel.json"):
        shutil.copyfile(ROOT / "services/api" / name, destination / name)
        copied.append(name)
    requirements = destination / "requirements.txt"
    text = requirements.read_text(encoding="utf-8")
    if "psutil" not in text:
        requirements.write_text(text.rstrip() + "\npsutil>=6.1,<8\n", encoding="utf-8")
    manifest = {
        "files": {name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
                  for name in sorted(copied)},
        "shared_runtime_included": (destination / "app/integrations/chatwoot.py").is_file(),
        "credentials_included": False,
    }
    (destination / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8",
    )
    (destination / ".vercel").mkdir()
    shutil.copyfile(ROOT / "services/api/.vercel/project.json",
                    destination / ".vercel/project.json")
    return {"directory": str(destination), "file_count": len(copied),
            "shared_runtime_included": manifest["shared_runtime_included"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare_release(args.output), indent=2))


if __name__ == "__main__":
    main()
