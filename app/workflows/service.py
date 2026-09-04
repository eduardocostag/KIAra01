from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class WorkflowSpec:
    name: str
    domain: str
    channel: str
    trigger_description: str
    response_policy: str
    action_policy: str
    escalation_policy: str
    id: str = ""
    enabled: bool = False
    status: str = "draft"
    created_at: str = ""

    def __post_init__(self) -> None:
        self.id = self.id or str(uuid.uuid4())
        self.created_at = self.created_at or datetime.now(UTC).isoformat()
        if self.status not in {"draft", "ready", "active", "paused"}:
            raise ValueError("Invalid workflow status")
        if self.enabled and self.status != "active":
            raise ValueError("Only active workflows can be enabled")


class WorkflowStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as database:
            database.execute(
                """CREATE TABLE IF NOT EXISTS workflows (
                       id TEXT PRIMARY KEY,
                       payload TEXT NOT NULL,
                       updated_at TEXT NOT NULL
                   )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    def save(self, workflow: WorkflowSpec) -> str:
        payload = json.dumps(asdict(workflow), ensure_ascii=False, sort_keys=True)
        with self._connect() as database:
            database.execute(
                """INSERT INTO workflows(id,payload,updated_at) VALUES(?,?,?)
                   ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,
                   updated_at=excluded.updated_at""",
                (workflow.id, payload, datetime.now(UTC).isoformat()),
            )
        return workflow.id

    def list(self) -> list[WorkflowSpec]:
        with self._connect() as database:
            rows = database.execute("SELECT payload FROM workflows ORDER BY updated_at DESC").fetchall()
        return [WorkflowSpec(**json.loads(row[0])) for row in rows]

    def get(self, workflow_id: str) -> WorkflowSpec | None:
        with self._connect() as database:
            row = database.execute(
                "SELECT payload FROM workflows WHERE id=?", (workflow_id,)
            ).fetchone()
        return WorkflowSpec(**json.loads(row[0])) if row else None


class ConversationalWorkflowBuilder:
    """Collect one operational rule at a time and save a disabled, reviewable workflow."""

    QUESTIONS = (
        (
            "trigger_description",
            (
                "O que o cliente ou o sistema deve dizer ou apresentar para iniciar esse fluxo? "
                "Inclua exemplos e informações que a Kiara deve coletar."
            ),
        ),
        (
            "response_policy",
            (
                "Como a Kiara deve atender? Informe tom, perguntas, o que pode responder e o que "
                "nunca deve prometer."
            ),
        ),
        (
            "action_policy",
            (
                "Depois de entender o contexto, quais ações ela deve preparar ou executar e em "
                "qual ordem? Separe ações automáticas das que exigem aprovação."
            ),
        ),
        (
            "escalation_policy",
            (
                "Quando ela deve parar, pedir confirmação ou transferir para uma pessoa? "
                "Informe também horários, riscos e exceções."
            ),
        ),
    )

    def __init__(self, store: WorkflowStore) -> None:
        self.store = store
        self._draft: dict[str, str] | None = None
        self._question_index = 0
        self._awaiting_confirmation = False

    @property
    def active(self) -> bool:
        return self._draft is not None

    def begin(self, request: str) -> str:
        normalized = request.casefold()
        channel = next(
            (item for item in ("whatsapp", "instagram", "telegram", "email") if item in normalized),
            "interno",
        )
        domain = next(
            (item for item in ("hardware", "software", "atendimento") if item in normalized),
            "operacional",
        )
        self._draft = {
            "name": request.strip()[:120],
            "domain": domain,
            "channel": channel,
        }
        self._question_index = 0
        self._awaiting_confirmation = False
        return (
            f"Vamos montar o fluxo de {domain} pelo canal {channel}, uma regra por vez. "
            + self.QUESTIONS[0][1]
            + " Você pode dizer 'cancelar fluxo' a qualquer momento."
        )

    def consume(self, message: str) -> str:
        if self._draft is None:
            raise RuntimeError("No workflow design is active")
        normalized = message.strip().casefold()
        if normalized in {"cancelar", "cancelar fluxo", "cancele o fluxo"}:
            self._reset()
            return "Cancelei o desenho do fluxo; nenhuma automação foi salva."
        if self._awaiting_confirmation:
            if normalized not in {"confirmar fluxo", "confirmo o fluxo", "confirmar"}:
                return (
                    "O fluxo ainda não foi salvo. Digite 'confirmar fluxo' para guardar o "
                    "rascunho desativado, ou 'cancelar fluxo'."
                )
            workflow = WorkflowSpec(**self._draft, status="ready", enabled=False)
            self.store.save(workflow)
            self._reset()
            return (
                f"Fluxo {workflow.id} salvo como pronto, mas desativado. Mensagens externas, "
                "mudanças no computador e demais ações sensíveis continuam exigindo "
                "conector configurado e aprovação conforme a política."
            )
        key, _question = self.QUESTIONS[self._question_index]
        if len(message.strip()) < 4:
            return "Preciso de um pouco mais de detalhe. " + self.QUESTIONS[self._question_index][1]
        self._draft[key] = message.strip()
        self._question_index += 1
        if self._question_index < len(self.QUESTIONS):
            return self.QUESTIONS[self._question_index][1]
        self._awaiting_confirmation = True
        return self._preview()

    def _preview(self) -> str:
        assert self._draft is not None
        return (
            "Revise o fluxo:\n"
            f"- Domínio: {self._draft['domain']}\n"
            f"- Canal: {self._draft['channel']}\n"
            f"- Gatilho e coleta: {self._draft['trigger_description']}\n"
            f"- Atendimento: {self._draft['response_policy']}\n"
            f"- Ações: {self._draft['action_policy']}\n"
            f"- Escalonamento: {self._draft['escalation_policy']}\n"
            "Digite 'confirmar fluxo' para salvar desativado ou 'cancelar fluxo'."
        )

    def _reset(self) -> None:
        self._draft = None
        self._question_index = 0
        self._awaiting_confirmation = False
