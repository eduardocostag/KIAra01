"""Local, bounded adapters for the pinned MIT Instagram content utilities."""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar

from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool

RESOURCE_ROOT = Path(__file__).resolve().parents[1] / "resources" / "instagram_agent"
SCRIPTS = {
    "hookscore": "ig-reel/hookscore.py",
    "beats": "ig-reel/beats.py",
    "caption": "ig-caption/caption.py",
    "humanize": "ig-human/humanize.py",
    "detect": "ig-human/detect.py",
    "swipe": "ig-viral/swipe.py",
}


@lru_cache(maxsize=6)
def _module(operation: str):
    path = RESOURCE_ROOT / "skills" / SCRIPTS[operation]
    spec = importlib.util.spec_from_file_location(f"kiara_ig_{operation}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Utilitario Instagram indisponivel.")
    module = importlib.util.module_from_spec(spec)
    previous_path = sys.path[:]
    try:
        spec.loader.exec_module(module)
    finally:
        # Upstream swipe adds its sibling directory to sys.path for hook scoring.
        sys.path[:] = previous_path
    return module


class InstagramContentCheckTool(Tool):
    name = "instagram_content_check"
    description = (
        "Analisa rascunhos Instagram localmente: hookscore, beats, caption, humanize, "
        "detect ou swipe. Heuristicas em ingles; nao publica nem preve viralizacao."
    )
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": list(SCRIPTS)},
            "text": {"type": "string", "maxLength": 12000},
            "target_seconds": {"type": "number", "minimum": 1, "maximum": 600},
            "wpm": {"type": "number", "minimum": 60, "maximum": 300},
            "keywords": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
            "reels": {
                "type": "array", "maxItems": 100,
                "items": {"type": "object", "properties": {
                    "account": {"type": "string"}, "hook": {"type": "string"},
                    "views": {"type": "integer"}, "median": {"type": "integer"},
                    "followers": {"type": "integer"},
                }, "required": ["account", "hook", "views"]},
            },
        },
        "required": ["operation"],
        "additionalProperties": False,
    }

    def audit_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        text, reels = parameters.get("text"), parameters.get("reels")
        return {"operation": parameters.get("operation"),
                "text_length": len(text) if isinstance(text, str) else 0,
                "reel_count": len(reels) if isinstance(reels, list) else 0}

    def validate(self, parameters: dict[str, Any]) -> None:
        if parameters.keys() - self.schema["properties"].keys():
            raise ValueError("Parametro Instagram desconhecido.")
        operation = parameters.get("operation")
        if not isinstance(operation, str) or operation not in SCRIPTS:
            raise ValueError("Operacao Instagram invalida.")
        text = parameters.get("text", "")
        if not isinstance(text, str) or len(text) > 12000:
            raise ValueError("Texto deve ter no maximo 12000 caracteres.")
        if operation != "swipe" and not text.strip():
            raise ValueError("Informe o texto do rascunho.")
        for key, default, low, high in (("wpm", 165, 60, 300),
                                        ("target_seconds", 30, 1, 600)):
            value = parameters.get(key, default)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not low <= value <= high):
                raise ValueError(f"{key} fora do limite.")
        keywords = parameters.get("keywords", [])
        if (not isinstance(keywords, list) or len(keywords) > 20
                or any(not isinstance(k, str) or len(k) > 100 for k in keywords)):
            raise ValueError("Keywords invalidas.")
        reels = parameters.get("reels", [])
        if not isinstance(reels, list) or len(reels) > 100:
            raise ValueError("Informe no maximo 100 reels.")
        if operation == "swipe" and not reels:
            raise ValueError("Informe os reels coletados manualmente.")
        for row in reels:
            if not isinstance(row, dict):
                raise TypeError("Reel invalido.")
            for key in ("account", "hook"):
                if not isinstance(row.get(key), str) or not 1 <= len(row[key]) <= 1000:
                    raise ValueError(f"{key} invalido.")
            for key in ("views", "followers", "median"):
                value = row.get(key)
                if value is None and key != "views":
                    continue
                if type(value) is not int or not 0 <= value <= 10**12:
                    raise ValueError(f"{key} invalido.")

    async def execute(self, **parameters: Any) -> ToolResult:
        self.validate(parameters)
        operation, text = parameters["operation"], parameters.get("text", "")
        module = _module(operation)
        if operation == "hookscore":
            checks, score, verdict, flags = module.run(text)
            result = {"checks": checks, "score": score, "verdict": verdict, "flags": flags}
        elif operation == "beats":
            result = module.analyse(text, wpm=parameters.get("wpm", 165),
                                    target=parameters.get("target_seconds"))
        elif operation == "caption":
            result = module.analyse(text, keywords=parameters.get("keywords", []))
        elif operation in {"humanize", "detect"}:
            lex = json.loads((RESOURCE_ROOT / "skills/ig-human/slop.json").read_text("utf-8"))
            if operation == "humanize":
                cleaned, report = module.humanize(text, lex)
                result = {"text": cleaned, "report": report}
            else:
                checks, score, verdict = module.run(text, lex)
                result = {"checks": checks, "score": score, "verdict": verdict}
        else:
            rows = [{key: row.get(key) for key in
                     ("account", "hook", "views", "median", "followers")}
                    for row in parameters["reels"]]
            result = module.analyse(rows, module.load_formulas(module.HOOKS))
        return ToolResult(True, output=json.dumps(result, ensure_ascii=False), metadata={
            "operation": operation, "local_only": True,
            "limitations": "Heuristicas em ingles; nao preve alcance ou detectores externos.",
        })
