"""Import a bounded, credential-free snapshot into Kiara's website skill.

Reads the source project and installed skill definitions; never installs packages,
clones repositories, invokes media services, or changes the source project.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "app/resources/operational_skills/kiara-web-studio"
ASSETS = Path("assets/landing-page-system")
UPSTREAM = Path("references/upstream-skills")
MANIFEST = SKILL / "references/source-manifest.json"
CATALOG = SKILL / "references/catalog.json"
LTX_SOURCE = Path(".tools/ltx-space-source")
LTX_DESTINATION = ASSETS / "upstream/ltx-video-distilled"
LTX_FILES = ("app.py", "README.md", "requirements.txt", "LICENSE", "LICENSE.md", "LICENSE.txt")
ROOT_FILES = {
    "README.md", "PLAYBOOK.md", "QUALITY-GATES.md", "PUBLISHING.md",
    "CINEMATIC-PIPELINE.md", ".gitignore", "LICENSE", "LICENSE.md", "LICENSE.txt",
}
TREES = {"templates", "config", "prompts", "scripts", "hf-space"}
SUFFIXES = {
    ".md", ".json", ".yaml", ".yml", ".html", ".css", ".js", ".mjs", ".py",
    ".ps1", ".txt", ".webp", ".png", ".jpg", ".jpeg", ".svg", ".avif", ".mp4", ".webm",
}
BLOCKED = {"__pycache__", "node_modules", ".git", ".tools", ".hf-home", "dist", "versions"}
SECRET = re.compile(r"(?:\bhf_[A-Za-z0-9]{30,}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b|"
                    r"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}\b|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
SKILLS = (
    ("imagegen", "system", "imagegen"),
    ("sites", "sites", "sites"),
    ("sites-remix", "sites", "sites-remix"),
    ("deployments-cicd", "vercel", "deployments-cicd"),
    ("vercel-cli", "vercel", "vercel-cli"),
    ("env-vars", "vercel", "env-vars"),
    ("domains", "vercel", "domains"),
    ("verification", "vercel", "verification"),
    ("react-best-practices", "vercel", "react-best-practices"),
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_file(path: Path, base: Path) -> None:
    for ancestor in [path, *path.parents]:
        if ancestor.is_symlink():
            raise ValueError(f"Symlink source rejected: {path.name}")
        if ancestor == base:
            break
    if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError(f"Unsafe source file: {path.name}")
    if path.stat().st_size > 12_000_000:
        raise ValueError(f"Snapshot file exceeds 12 MB: {path.name}")
    if (path.suffix.lower() in SUFFIXES - {".webp", ".png", ".jpg", ".jpeg", ".avif", ".mp4", ".webm"}
            and SECRET.search(path.read_text(encoding="utf-8-sig"))):
        raise ValueError(f"Credential-like content rejected: {path.name}")


def walk_sources(base: Path, tree: str):
    folder = base / tree
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError(f"Missing or unsafe source folder: {tree}")
    for current, dirs, files in os.walk(folder, followlinks=False):
        parent = Path(current)
        dirs[:] = sorted(name for name in dirs if name not in BLOCKED and not name.startswith(".env"))
        for name in dirs:
            if (parent / name).is_symlink():
                raise ValueError(f"Symlink source folder rejected: {name}")
        for name in sorted(files):
            path = parent / name
            if name.startswith(".env") or name.lower() in {"token", "stored_tokens", "credentials.json", "auth.json"}:
                continue
            if path.suffix.lower() in SUFFIXES or name == ".gitignore":
                checked_file(path, base)
                yield path


def skill_location(codex: Path, package: str, name: str) -> Path:
    if package == "system":
        result = codex / "skills/.system" / name
    else:
        cache = codex / "plugins/cache/openai-curated-remote" / package
        candidates = [p for p in cache.glob(f"*/skills/{name}") if p.is_dir()]
        if not candidates:
            raise ValueError(f"Installed skill not found: {package}:{name}")

        def version(path: Path):
            return tuple(int(value) for value in re.findall(r"\d+", path.parents[1].name))

        result = max(candidates, key=version)
    if result.is_symlink() or not (result / "SKILL.md").is_file():
        raise ValueError(f"Missing or unsafe skill: {name}")
    return result


def target_path(relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe snapshot destination")
    if not (relative.is_relative_to(ASSETS) or relative.is_relative_to(UPSTREAM)):
        raise ValueError("Destination outside importer-owned prefixes")
    candidate = SKILL / relative
    for part in [candidate, *candidate.parents]:
        if part == SKILL.parent:
            break
        if part.is_symlink():
            raise ValueError("Symlink snapshot destination rejected")
    if not candidate.resolve().is_relative_to(SKILL.resolve()):
        raise ValueError("Snapshot destination escapes skill")
    return candidate


def verify_snapshot() -> dict:
    if MANIFEST.is_symlink() or CATALOG.is_symlink():
        raise ValueError("Unsafe manifest")
    if MANIFEST.stat().st_size > 100_000 or CATALOG.stat().st_size > 20_000:
        raise ValueError("Skill reference exceeds its full-read size limit")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if json.loads(CATALOG.read_text(encoding="utf-8")) != catalog_data(manifest):
        raise ValueError("Catalog is inconsistent with the source manifest")
    for item in manifest["files"]:
        path = target_path(Path(item["path"]))
        if not path.is_file() or path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise ValueError(f"Snapshot integrity mismatch: {item['path']}")
    listed = {item["path"] for item in manifest["files"]}
    if len(listed) != len(manifest["files"]):
        raise ValueError("Duplicate source-manifest entries")
    actual = {p.relative_to(SKILL).as_posix() for root in (SKILL / ASSETS, SKILL / UPSTREAM)
              for p in root.rglob("*") if p.is_file()}
    if actual != listed:
        raise ValueError("Snapshot contains unmanaged or missing files")
    templates = sorted(p.parent.name for p in (SKILL / ASSETS / "templates").glob("*/index.html"))
    if templates != [entry["name"] for entry in manifest["templates"]]:
        raise ValueError("Template inventory mismatch")
    return {"verified": True, "files": len(listed), "templates": len(templates), "skills": len(manifest["skills"])}


def catalog_data(manifest: dict) -> dict:
    return {**{key: manifest[key] for key in ("version", "status", "repositories", "templates", "segments", "skills")},
            "integrity_check": "python scripts/import_landing_page_system.py --verify"}


def write_reference(path: Path, value: dict, *, compact: bool = False) -> None:
    if path not in {MANIFEST, CATALOG}:
        raise ValueError("Reference outside importer ownership")
    for ancestor in [path, *path.parents]:
        if ancestor.is_symlink():
            raise ValueError("Unsafe reference destination")
        if ancestor == SKILL:
            break
    if not path.resolve().is_relative_to(SKILL.resolve()):
        raise ValueError("Unsafe reference destination")
    text = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) if compact
            else json.dumps(value, ensure_ascii=False, indent=2)) + "\n"
    if len(text.encode("utf-8")) > (100_000 if path == MANIFEST else 20_000):
        raise ValueError("Reference too large for the operational skill reader")
    temporary = path.with_name(path.name + ".import-tmp")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("Unexpected temporary reference")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def import_snapshot(source: Path, codex: Path) -> dict:
    if source.is_symlink():
        raise ValueError("Symlink source root rejected")
    source = source.resolve()
    if not source.is_dir():
        raise ValueError("Landing Page System source does not exist")
    plan: list[tuple[Path, Path, str]] = []
    for name in sorted(ROOT_FILES):
        path = source / name
        if path.exists():
            checked_file(path, source)
            plan.append((path, ASSETS / name, "landing-page-system"))
    for tree in sorted(TREES):
        for path in walk_sources(source, tree):
            plan.append((path, ASSETS / path.relative_to(source), "landing-page-system"))
    # Narrow, explicit exception: these are model/Space source files already
    # present locally, not the .tools dependency tree, cache or model weights.
    ltx_evidence = []
    for name in LTX_FILES:
        path = source / LTX_SOURCE / name
        if path.exists() or path.is_symlink():
            checked_file(path, source)
            relative = LTX_DESTINATION / name
            plan.append((path, relative, "ltx-video-distilled-local-source"))
            ltx_evidence.append(relative.as_posix())
    skills = []
    for label, package, name in SKILLS:
        location = skill_location(codex, package, name)
        inputs = [location / "SKILL.md"]
        if (location / "references").is_dir():
            inputs.extend(p for p in (location / "references").rglob("*")
                          if p.is_file() and p.suffix.lower() in {".md", ".json", ".yaml", ".yml"})
        inputs.extend(location / name for name in ("LICENSE", "LICENSE.txt", "LICENSE.md") if (location / name).is_file())
        for path in sorted(inputs):
            checked_file(path, location)
            plan.append((path, UPSTREAM / label / path.relative_to(location), label))
        skills.append({"name": label, "source": str(location), "status": "reference_only",
                       "entrypoint": (UPSTREAM / label / "SKILL.md").as_posix(),
                       "activation": "Requires the corresponding host skill/plugin and its own authorization; copying is not activation."})
    files = []
    # Validate every input/destination before the first write.
    for origin, relative, _ in plan:
        checked_file(origin, origin.parent if relative.is_relative_to(UPSTREAM) else source)
        target_path(relative)
    for origin, relative, owner in plan:
        destination = target_path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".import-tmp")
        if temporary.exists() or temporary.is_symlink():
            raise ValueError("Unexpected temporary import file")
        try:
            temporary.write_bytes(origin.read_bytes())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        files.append({"path": relative.as_posix(), "owner": owner,
                      "bytes": destination.stat().st_size, "sha256": digest(destination)})
    templates = []
    for entry in sorted((source / "templates").iterdir()):
        if entry.is_dir() and (entry / "index.html").is_file():
            selected = [item for item in files if item["path"].startswith((ASSETS / "templates" / entry.name).as_posix() + "/")]
            templates.append({"name": entry.name, "segment": entry.name.split("-template")[0],
                              "files": len(selected), "bytes": sum(item["bytes"] for item in selected)})
    manifest = {
        "version": 1, "source_root": str(source), "status": "reference_only",
        "remote_repositories_cloned": False, "credentials_copied": False, "services_invoked": False,
        "excluded": sorted(BLOCKED | {".env*", "media-source/generated", "verification captures"}),
        "repositories": [
            {"id": "landing-page-system", "kind": "local_project", "source": str(source), "status": "snapshot_imported", "remote": None},
            {"id": "eduardocostag/landing-cinema-generator", "kind": "huggingface_space", "url": "https://huggingface.co/spaces/eduardocostag/landing-cinema-generator", "engine": "light", "status": "reference_only"},
            {"id": "Lightricks/ltx-video-distilled", "kind": "huggingface_space", "url": "https://huggingface.co/spaces/Lightricks/ltx-video-distilled", "engine": "real", "default": True, "status": "reference_only", "local_source": str(source / LTX_SOURCE), "evidence": ltx_evidence},
            {"id": "Lightricks/LTX-Video", "kind": "github_repository", "url": "https://github.com/Lightricks/LTX-Video", "status": "reference_only", "evidence": ltx_evidence},
            {"id": "Lightricks/LTX-Video", "kind": "huggingface_model", "url": "https://huggingface.co/Lightricks/LTX-Video", "checkpoint": "ltxv-13b-0.9.8-distilled.safetensors", "status": "reference_only", "evidence": ltx_evidence},
        ],
        "source_exceptions": {LTX_SOURCE.as_posix(): {"allowlist": list(LTX_FILES), "imported": ltx_evidence}},
        "templates": templates, "segments": dict(Counter(item["segment"] for item in templates)),
        "skills": skills, "files": sorted(files, key=lambda item: item["path"]),
    }
    # Compact file hashes keep the manifest below OperationalSkills' 100 KB
    # resource limit. Origins are recorded once per project/installed skill.
    write_reference(MANIFEST, manifest, compact=True)
    write_reference(CATALOG, catalog_data(manifest))
    return verify_snapshot()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.home() / "Desktop/sites/landing-page-system")
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = verify_snapshot() if args.verify else import_snapshot(args.source, args.codex_home)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
