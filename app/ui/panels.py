from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app import autostart
from app.automation import AutomationSpec, AutomationTeacher, TriggerKind, automation_template
from app.models import AutonomyMode


def _confirm(parent: QWidget, title: str, message: str) -> bool:
    return QMessageBox.question(parent, title, message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes


class InfoPanel(QWidget):
    def __init__(self, loader: Callable[[], object], empty_message: str) -> None:
        super().__init__(); self._loader, self._empty_message = loader, empty_message
        self.output = QTextBrowser(accessibleName=empty_message)
        refresh = QPushButton("Atualizar"); refresh.clicked.connect(self.refresh)
        layout = QVBoxLayout(self); layout.addWidget(self.output, 1); layout.addWidget(refresh)
        self.refresh()

    def refresh(self) -> None:
        try:
            value = self._loader()
            self.output.setPlainText(self._empty_message if not value else value if isinstance(value, str)
                                     else json.dumps(value, ensure_ascii=False, indent=2, default=str))
        except Exception as exc:  # noqa: BLE001
            self.output.setPlainText(f"Não foi possível carregar: {exc}")


class AutomationPanel(QWidget):
    """Validated, preview-first automation administration."""
    def __init__(self, core) -> None:
        super().__init__(); self.engine = core.background.automations
        self.items = QListWidget(accessibleName="Automações cadastradas")
        self.name, self.trigger_value = QLineEdit(), QLineEdit()
        self.name.setAccessibleName("Nome da automação")
        self.trigger_value.setPlaceholderText("ISO, segundos, evento ou condição JSON")
        self.trigger_value.setAccessibleName("Valor do gatilho")
        self.trigger = QComboBox(); self.trigger.setAccessibleName("Tipo de gatilho")
        self.trigger.addItems([kind.value for kind in TriggerKind])
        self.action = QComboBox(); self.action.setAccessibleName("Ação da automação")
        self.action.addItems(core.tools.names())
        self.parameters = QLineEdit("{}"); self.parameters.setAccessibleName("Parâmetros JSON")
        self.templates = QComboBox(accessibleName="Modelos de automação")
        self.templates.addItems(["abrir_portal_diariamente", "avisar_erro_detectado"])
        self.preview = QTextBrowser(accessibleName="Prévia da automação"); self.preview.setMaximumHeight(120)
        self.history = QTextBrowser(accessibleName="Histórico de execuções"); self.history.setMaximumHeight(100)
        form = QFormLayout()
        for label, widget in (("Nome", self.name), ("Gatilho", self.trigger), ("Valor", self.trigger_value),
                              ("Ação", self.action), ("Parâmetros", self.parameters)): form.addRow(label, widget)
        buttons = QHBoxLayout()
        self._selection_buttons: list[QPushButton] = []
        for label, slot in (("Aplicar modelo", self.apply_template), ("Ver prévia", self.show_preview),
                            ("Ensinar rascunho", self.teach_draft), ("Criar", self.create),
                            ("Ativar/desativar", self.toggle_selected), ("Excluir", self.delete_selected)):
            button = QPushButton(label); button.clicked.connect(slot); buttons.addWidget(button)
            if label in {"Ativar/desativar", "Excluir"}: self._selection_buttons.append(button)
        layout = QVBoxLayout(self); layout.addWidget(self.items, 1); layout.addWidget(self.templates); layout.addLayout(form)
        layout.addWidget(self.preview); layout.addLayout(buttons); layout.addWidget(self.history)
        self.items.currentItemChanged.connect(self._update_selection_actions)
        self.refresh()

    def _update_selection_actions(self) -> None:
        selected = self.items.currentItem() is not None
        for button in self._selection_buttons:
            button.setEnabled(selected)

    def apply_template(self) -> None:
        spec = automation_template(self.templates.currentText())
        self.name.setText(spec.name); self.trigger.setCurrentText(spec.trigger_kind.value)
        self.trigger_value.setText(str(spec.interval_seconds or spec.trigger_value))
        self.action.setCurrentText(spec.action)
        self.parameters.setText(json.dumps(spec.action_parameters, ensure_ascii=False)); self.show_preview()

    def teach_draft(self) -> None:
        try:
            spec = AutomationTeacher().prepare(name=self.name.text().strip(), action=self.action.currentText(), parameters=json.loads(self.parameters.text()))
            self.preview.setPlainText(json.dumps(self.engine.preview(spec), ensure_ascii=False, indent=2))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.preview.setPlainText(f"Rascunho inválido: {exc}")

    def _draft(self) -> AutomationSpec:
        kind, raw = TriggerKind(self.trigger.currentText()), self.trigger_value.text().strip()
        kwargs: dict[str, object] = {"trigger_value": raw}
        if kind == TriggerKind.RECURRING: kwargs = {"interval_seconds": float(raw)}
        elif kind == TriggerKind.SCHEDULED: kwargs = {"next_run_at": raw}
        return AutomationSpec(name=self.name.text().strip(), trigger_kind=kind,
            action=self.action.currentText(), action_parameters=json.loads(self.parameters.text()), **kwargs)

    def show_preview(self) -> AutomationSpec | None:
        try:
            spec = self._draft()
            if not spec.name or not spec.action: raise ValueError("Nome e ação são obrigatórios")
            self.preview.setPlainText(json.dumps(self.engine.preview(spec), ensure_ascii=False, indent=2))
            return spec
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.preview.setPlainText(f"Prévia inválida: {exc}"); return None

    def create(self) -> None:
        spec = self.show_preview()
        if spec and _confirm(self, "Criar automação", f"Criar esta automação?\n\n{self.preview.toPlainText()}"):
            try: self.engine.add(spec); self.refresh()
            except (ValueError, TypeError, json.JSONDecodeError) as exc: QMessageBox.warning(self, "Automação inválida", str(exc))

    def _selected(self):
        item = self.items.currentItem()
        return self.engine.store.get(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def toggle_selected(self) -> None:
        spec = self._selected()
        if spec and _confirm(self, "Alterar automação", f"{('Desativar' if spec.enabled else 'Ativar')} “{spec.name}”? "):
            self.engine.set_enabled(spec.id, not spec.enabled); self.refresh()

    def delete_selected(self) -> None:
        spec = self._selected()
        if spec and _confirm(self, "Excluir automação", f"Excluir permanentemente “{spec.name}”? "):
            self.engine.remove(spec.id); self.refresh()

    def refresh(self) -> None:
        self.items.clear()
        for spec in self.engine.store.list():
            state = "Ativa" if spec.enabled else "Inativa"
            item = QListWidgetItem(f"{state}: {spec.name} — {spec.trigger_kind.value} → {spec.action}")
            item.setData(Qt.ItemDataRole.UserRole, spec.id); self.items.addItem(item)
        self.history.setPlainText(json.dumps(self.engine.store.list_runs(limit=20), ensure_ascii=False, indent=2))
        self._update_selection_actions()


class AuditPanel(QWidget):
    """Unified, redacted operational timeline with explicit export."""

    def __init__(self, core) -> None:
        super().__init__(); self.audit = core.tools.audit
        self.timeline = QTextBrowser(accessibleName="Linha do tempo de auditoria")
        refresh = QPushButton("Atualizar"); refresh.clicked.connect(self.refresh)
        export = QPushButton("Exportar auditoria redigida"); export.clicked.connect(self.export)
        row = QHBoxLayout(); row.addWidget(refresh); row.addWidget(export)
        layout = QVBoxLayout(self); layout.addWidget(self.timeline, 1); layout.addLayout(row); self.refresh()

    def refresh(self) -> None:
        self.timeline.setPlainText(json.dumps(self.audit.read(limit=200), ensure_ascii=False, indent=2))

    def export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar auditoria", "kiara-audit.jsonl", "JSON Lines (*.jsonl)")
        if path and _confirm(self, "Exportar auditoria", "Exportar a linha do tempo já redigida?"):
            try:
                count = self.audit.export(Path(path))
                QMessageBox.information(self, "Auditoria exportada", f"{count} eventos exportados.")
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Falha na exportação", str(exc))


class MemoryPanel(QWidget):
    def __init__(self, core) -> None:
        super().__init__(); self.memory = getattr(core.context, "_memory", None)
        self.knowledge = getattr(core.context, "_knowledge", None)
        self.memories = QListWidget(accessibleName="Registros de memória")
        self.documents = QListWidget(accessibleName="Documentos de conhecimento")
        forget = QPushButton("Esquecer memória selecionada"); forget.clicked.connect(self.forget_memory)
        ingest = QPushButton("Ingerir documento"); ingest.clicked.connect(self.ingest_document)
        remove = QPushButton("Remover documento selecionado"); remove.clicked.connect(self.forget_document)
        self._memory_action, self._document_action = forget, remove
        memory_label = QLabel("Memórias locais"); memory_label.setBuddy(self.memories)
        document_label = QLabel("Base de conhecimento"); document_label.setBuddy(self.documents)
        layout = QVBoxLayout(self); layout.addWidget(memory_label); layout.addWidget(self.memories, 1)
        layout.addWidget(forget); layout.addWidget(document_label); layout.addWidget(self.documents, 1)
        row = QHBoxLayout(); row.addWidget(ingest); row.addWidget(remove); layout.addLayout(row); self.refresh()
        self.memories.currentItemChanged.connect(self._update_selection_actions)
        self.documents.currentItemChanged.connect(self._update_selection_actions)
        self._update_selection_actions()

    def _update_selection_actions(self) -> None:
        self._memory_action.setEnabled(self.memories.currentItem() is not None)
        self._document_action.setEnabled(self.documents.currentItem() is not None)

    def refresh(self) -> None:
        self.memories.clear(); self.documents.clear()
        if self.memory:
            for record in self.memory.list_records():
                item = QListWidgetItem(f"#{record.id} [{record.kind.value}] {record.content}")
                item.setData(Qt.ItemDataRole.UserRole, record.id); self.memories.addItem(item)
        if self.knowledge:
            for document in self.knowledge.list_documents():
                item = QListWidgetItem(f"#{document['id']} {Path(document['source']).name} ({document['chunks']} trechos)")
                item.setData(Qt.ItemDataRole.UserRole, document["id"]); self.documents.addItem(item)
        self._update_selection_actions()

    def forget_memory(self) -> None:
        item = self.memories.currentItem()
        if self.memory and item and _confirm(self, "Esquecer memória", f"Excluir permanentemente?\n\n{item.text()}"):
            self.memory.forget(int(item.data(Qt.ItemDataRole.UserRole))); self.refresh()

    def ingest_document(self) -> None:
        if not self.knowledge: return
        path, _ = QFileDialog.getOpenFileName(self, "Ingerir conhecimento", "", "Documentos (*.txt *.md *.pdf)")
        if path and _confirm(self, "Ingerir documento", f"Adicionar à base local?\n\n{path}"):
            try: self.knowledge.ingest(path); self.refresh()
            except (OSError, ValueError, RuntimeError) as exc: QMessageBox.warning(self, "Falha na ingestão", str(exc))

    def forget_document(self) -> None:
        item = self.documents.currentItem()
        if self.knowledge and item and _confirm(self, "Remover conhecimento", f"Excluir documento e seus trechos?\n\n{item.text()}"):
            self.knowledge.forget_document(int(item.data(Qt.ItemDataRole.UserRole))); self.refresh()


class SettingsPanel(InfoPanel):
    def __init__(self, loader: Callable[[], object], core=None) -> None:
        super().__init__(loader, "Configuração indisponível"); self.core = core
        self.autostart = QCheckBox("Iniciar Kiara ao entrar no Windows"); self.autostart.setChecked(autostart.is_enabled())
        self.autostart.toggled.connect(self._change_autostart); self.layout().insertWidget(1, self.autostart)
        if core is not None:
            self.autonomy = QComboBox(accessibleName="Nível de autonomia")
            self.autonomy.addItems([mode.value for mode in AutonomyMode]); self.autonomy.setCurrentText(core.tools.permission_gate.mode.value)
            apply = QPushButton("Aplicar autonomia nesta sessão"); apply.clicked.connect(self._change_autonomy)
            self.layout().insertWidget(2, self.autonomy); self.layout().insertWidget(3, apply)

    def _change_autostart(self, enabled: bool) -> None:
        if enabled and not _confirm(self, "Ativar inicialização automática", "Permitir que a Kiara inicie ao entrar no Windows?"):
            self.autostart.blockSignals(True); self.autostart.setChecked(False); self.autostart.blockSignals(False); return
        autostart.enable() if enabled else autostart.disable()

    def _change_autonomy(self) -> None:
        mode, current = AutonomyMode(self.autonomy.currentText()), self.core.tools.permission_gate.mode
        if mode == current: return
        if not _confirm(self, "Alterar autonomia", f"Alterar autonomia de “{current.value}” para “{mode.value}” nesta sessão?"):
            self.autonomy.setCurrentText(current.value); return
        self.core.tools.permission_gate.mode = mode
        self.core.settings.raw.setdefault("autonomy", {})["mode"] = mode.value; self.refresh()


def automation_snapshot(core) -> list[dict[str, object]]:
    background = getattr(core, "background", None)
    if background is None: return []
    return [{"name": i.name, "trigger": i.trigger_kind.value, "action": i.action,
             "enabled": i.enabled, "next_run_at": i.next_run_at} for i in background.automations.store.list()]


def memory_snapshot(core) -> dict[str, object]:
    memory, knowledge = getattr(core.context, "_memory", None), getattr(core.context, "_knowledge", None)
    return {"memory_enabled": memory is not None, "memory_records": memory.count() if memory else 0,
            "knowledge_enabled": knowledge is not None, "knowledge_documents": knowledge.document_count() if knowledge else 0,
            "knowledge_chunks": knowledge.chunk_count() if knowledge else 0}


def agent_snapshot(core) -> list[dict[str, object]]:
    agents = (*core.agent_router.specialists, core.agent_router.generalist)
    return [{"name": a.name, "description": a.description, "context": sorted(a.context_keys)} for a in agents]


def permission_snapshot(core) -> dict[str, object]:
    settings, tools = getattr(core, "settings", None), core.tools
    return {"autonomy_mode": tools.permission_gate.mode.value,
            "kill_switch_active": bool(tools.kill_switch and tools.kill_switch.stopped),
            "tools": [{"name": name, "permission": tools.permission_level(name).value} for name in tools.names()],
            "llm_provider": settings.get("llm.provider", "local") if settings else "unknown",
            "llm_capabilities": sorted(core.llm.capabilities)}
