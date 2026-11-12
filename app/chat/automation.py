from __future__ import annotations

import platform
import threading
import time
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

import psutil

from app.chat.auth import SiteIdentity
from app.chat.service import ChatError
from app.models import AutonomyMode, PermissionLevel, ToolResult
from app.security.audit import AuditLog
from app.security.kill_switch import KillSwitch
from app.security.permissions import PermissionGate
from app.tools.base import Tool
from app.tools.registry import ToolRegistry


class LocalDiagnosticsTool(Tool):
    name = "chat_local_diagnostics"
    description = "Lê sistema operacional, uso de CPU e memória; não lista arquivos ou processos."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict] = {"properties": {}, "required": []}

    def validate(self, parameters):
        if parameters:
            raise ValueError("Diagnóstico não aceita comandos ou parâmetros.")

    async def execute(self, **parameters):
        memory = psutil.virtual_memory()
        return ToolResult(True, output=f"Sistema: {platform.system()} {platform.release()}. CPU: {psutil.cpu_percent()}%. Memória em uso: {memory.percent}%. Nenhum arquivo ou processo foi consultado.")


class ControlledAutomation:
    """Single-use typed plans scoped to user+organization. No LLM-generated command runs."""

    def __init__(self, audit_path: Path):
        self.kill_switch = KillSwitch()
        self.audit = AuditLog(audit_path)
        self.registry = ToolRegistry(PermissionGate(AutonomyMode.EXECUTE_WITH_CONFIRMATION),
                                     self.audit, self.kill_switch)
        self.registry.register(LocalDiagnosticsTool())
        self._plans: dict[str, dict] = {}
        self._lock = threading.Lock()

    def prepare(self, prompt: str, identity: SiteIdentity) -> dict | None:
        # This is the entire executable catalog, intentionally deterministic.
        if not any(word in prompt.casefold() for word in ("diagnóstico", "diagnostico", "uso de cpu", "uso de memória", "uso de memoria")):
            return None
        now = time.monotonic()
        plan_id = str(uuid4())
        with self._lock:
            self._plans = {key: value for key, value in self._plans.items() if value["expires"] > now}
            if len(self._plans) >= 100:
                raise ChatError(429, "Há muitos planos pendentes. Aguarde alguns minutos.")
            self._plans[plan_id] = {"user": identity.user_id, "organization": identity.organization_id,
                                    "expires": now + 300, "tool": "chat_local_diagnostics"}
        return {"text": "Plano preparado. O diagnóstico só será executado após sua aprovação.",
                "plan": {"id": plan_id, "steps": ["Ler sistema operacional, percentual de CPU e memória.", "Retornar o resultado e registrar auditoria sem conteúdo da conversa."],
                         "requires_approval": True, "execution_available": True,
                         "expires_in_seconds": 300}}

    async def execute(self, payload: dict, identity: SiteIdentity) -> dict:
        if payload.get("approved") is not True or set(payload) != {"plan_id", "approved"}:
            raise ChatError(422, "A execução exige somente plan_id e approved=true.")
        identifier = payload.get("plan_id")
        if not isinstance(identifier, str):
            raise ChatError(422, "Plano inválido.")
        with self._lock:
            plan = self._plans.get(identifier)
            if not plan or plan["expires"] <= time.monotonic():
                raise ChatError(409, "Plano inexistente, expirado ou já consumido.")
            if plan["user"] != identity.user_id or plan["organization"] != identity.organization_id:
                raise ChatError(403, "Este plano pertence a outra sessão.")
            del self._plans[identifier]
        result = await self.registry.execute(plan["tool"])
        self.audit.record(event="chat_plan_executed", plan_id=identifier,
                          user_id=identity.user_id, organization_id=identity.organization_id,
                          success=result.success, tool=plan["tool"])
        if not result.success:
            raise ChatError(409, "A execução foi interrompida pelo controle local. Prepare outro plano após reiniciar a ponte.")
        return {"text": result.output, "execution": {"plan_id": identifier, "success": True,
                "validated": True, "tool": plan["tool"]}}

    def stop(self) -> dict:
        self.kill_switch.trigger()
        with self._lock:
            self._plans.clear()
        return {"text": "Execução local interrompida. Reinicie a ponte para autorizar novas tarefas.", "stopped": True}
