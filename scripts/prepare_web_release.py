"""Prepare a clean monorepo-shaped frontend upload for the existing Vercel project."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def prepare_release() -> dict[str, object]:
    destination = ROOT / ".release" / f"kiara-web-{uuid4().hex[:12]}"
    target = destination / "apps/web"
    target.mkdir(parents=True, exist_ok=False)
    copied = []
    source = ROOT / "apps/web"
    for folder in ("src", "public"):
        for path in sorted((source / folder).rglob("*")):
            relative = path.relative_to(source)
            if (not path.is_file() or path.is_symlink()
                    or any(part.startswith(".env") for part in relative.parts)):
                continue
            output = target / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, output)
            copied.append(relative.as_posix())
    for name in ("package.json", "package-lock.json", "tsconfig.json", "next-env.d.ts",
                 "next.config.ts", "postcss.config.mjs", "eslint.config.mjs", "components.json"):
        path = source / name
        if path.is_file():
            shutil.copyfile(path, target / name)
            copied.append(name)
    (destination / ".vercel").mkdir()
    shutil.copyfile(ROOT / ".vercel/project.json", destination / ".vercel/project.json")
    (destination / "release-manifest.json").write_text(
        json.dumps({"files": sorted(copied), "credentials_included": False}, indent=2),
        encoding="utf-8",
    )
    return {"directory": str(destination), "file_count": len(copied)}


if __name__ == "__main__":
    print(json.dumps(prepare_release(), indent=2))
