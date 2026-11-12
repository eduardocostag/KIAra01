"""Verify the modular addition preserves the captured commercial source and contract.

Read-only: does not import the application, connect services, or update baselines.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
APPROVED_EXISTING_FILES = frozenset({
    "apps/web/src/components/app-shell/app-shell.tsx",
    "services/api/kiara_api/main.py",
})


def inspect_preservation(root: Path = ROOT) -> dict[str, object]:
    evidence = root / "evidence/kiara-modular"
    baseline = json.loads((evidence / "baseline.json").read_text(encoding="utf-8"))
    operations = json.loads((evidence / "api-contract-baseline.json").read_text(encoding="utf-8"))
    current = yaml.safe_load((root / "packages/contracts/openapi.yaml").read_text(encoding="utf-8"))
    unchanged, allowed_changes, unexpected_changes, missing = [], [], [], []
    for relative, expected in baseline["files"].items():
        path = root / relative
        if not path.is_file():
            missing.append(relative)
        elif hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            unchanged.append(relative)
        elif relative in APPROVED_EXISTING_FILES:
            allowed_changes.append(relative)
        else:
            unexpected_changes.append(relative)
    paths = current["paths"]
    changed_operations = [path for path, expected in operations.items() if paths.get(path) != expected]
    unexpected_paths = [path for path in paths if path not in operations and not (
        path == "/v1/platform" or path.startswith("/v1/platform/")
    )]
    passed = not (missing or unexpected_changes or changed_operations or unexpected_paths)
    return {
        "passed": passed,
        "baseline_commit": baseline["commit"],
        "baseline_branch": baseline["branch"],
        "baseline_file_count": len(baseline["files"]),
        "unchanged_count": len(unchanged),
        "approved_files_requiring_diff_review": allowed_changes,
        "missing_files": missing,
        "unexpected_source_changes": unexpected_changes,
        "baseline_contract_paths": len(operations),
        "changed_contract_paths": changed_operations,
        "unexpected_contract_paths": unexpected_paths,
        "new_platform_contract_paths": sorted(path for path in paths if path not in operations),
    }


def main() -> None:
    report = inspect_preservation()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
