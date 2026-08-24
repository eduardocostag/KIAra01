from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from app.automation import AutomationEngine, AutomationStore
from app.config import Settings
from app.knowledge import KnowledgeStore
from app.memory import MemoryEngine, MemoryKind
from app.models import AutonomyMode, PermissionLevel
from app.security.permissions import PermissionGate

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from app.ui.panels import AutomationPanel, MemoryPanel, SettingsPanel


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


class FakeTools:
    def __init__(self) -> None:
        self.permission_gate = PermissionGate(AutonomyMode.OBSERVE)
        self.kill_switch = None

    @staticmethod
    def names():
        return ["open_url"]

    @staticmethod
    def permission_level(_name):
        return PermissionLevel.SAFE_ACTION


def make_core(tmp_path):
    engine = AutomationEngine(AutomationStore(tmp_path / "automations.db"), lambda _spec: None)
    memory = MemoryEngine(tmp_path / "memory.db")
    knowledge = KnowledgeStore(tmp_path / "knowledge.db")
    return SimpleNamespace(
        background=SimpleNamespace(automations=engine),
        tools=FakeTools(),
        context=SimpleNamespace(_memory=memory, _knowledge=knowledge),
        settings=Settings(raw={"autonomy": {"mode": "observe"}}, root=tmp_path),
        llm=SimpleNamespace(capabilities=set()),
    )


def test_automation_panel_create_toggle_delete_with_preview(qt_app, tmp_path, monkeypatch) -> None:
    core = make_core(tmp_path)
    monkeypatch.setattr("app.ui.panels._confirm", lambda *_args: True)
    panel = AutomationPanel(core)
    panel.name.setText("Abrir portal")
    panel.trigger.setCurrentText("event")
    panel.trigger_value.setText("USER_READY")
    panel.parameters.setText('{"url": "https://example.com"}')

    panel.create()
    assert "Abrir portal" in panel.preview.toPlainText()
    assert panel.items.count() == 1
    panel.items.setCurrentRow(0)
    panel.toggle_selected()
    assert core.background.automations.store.list()[0].enabled is False
    panel.items.setCurrentRow(0)
    panel.delete_selected()
    assert core.background.automations.store.list() == []
    panel.close(); core.context._memory.close(); core.context._knowledge.close()


def test_management_panels_expose_accessible_names_and_selection_state(qt_app, tmp_path) -> None:
    core = make_core(tmp_path)
    automation = AutomationPanel(core)
    assert automation.name.accessibleName() == "Nome da automação"
    assert automation.trigger.accessibleName() == "Tipo de gatilho"
    assert automation.action.accessibleName() == "Ação da automação"
    assert all(not button.isEnabled() for button in automation._selection_buttons)

    memory = MemoryPanel(core)
    assert memory.memories.accessibleName() == "Registros de memória"
    assert memory.documents.accessibleName() == "Documentos de conhecimento"
    assert not memory._memory_action.isEnabled()
    assert not memory._document_action.isEnabled()
    automation.close(); memory.close()
    core.context._memory.close(); core.context._knowledge.close()


def test_memory_panel_forget_ingest_and_remove(qt_app, tmp_path, monkeypatch) -> None:
    core = make_core(tmp_path)
    core.context._memory.remember(MemoryKind.SEMANTIC, "segredo removível")
    document = tmp_path / "manual.txt"; document.write_text("conteúdo seguro", encoding="utf-8")
    monkeypatch.setattr("app.ui.panels._confirm", lambda *_args: True)
    monkeypatch.setattr("app.ui.panels.QFileDialog.getOpenFileName", lambda *_args: (str(document), ""))
    panel = MemoryPanel(core)
    panel.memories.setCurrentRow(0); panel.forget_memory()
    assert core.context._memory.count() == 0
    panel.ingest_document(); assert core.context._knowledge.document_count() == 1
    panel.documents.setCurrentRow(0); panel.forget_document()
    assert core.context._knowledge.document_count() == 0
    assert core.context._knowledge.chunk_count() == 0
    panel.close(); core.context._memory.close(); core.context._knowledge.close()


def test_autonomy_change_requires_confirmation(qt_app, tmp_path, monkeypatch) -> None:
    core = make_core(tmp_path)
    monkeypatch.setattr("app.ui.panels.autostart.is_enabled", lambda: False)
    panel = SettingsPanel(dict, core)
    panel.autonomy.setCurrentText(AutonomyMode.EXECUTE_WITH_CONFIRMATION.value)
    monkeypatch.setattr("app.ui.panels._confirm", lambda *_args: False)
    panel._change_autonomy()
    assert core.tools.permission_gate.mode == AutonomyMode.OBSERVE
    monkeypatch.setattr("app.ui.panels._confirm", lambda *_args: True)
    panel.autonomy.setCurrentText(AutonomyMode.EXECUTE_WITH_CONFIRMATION.value)
    panel._change_autonomy()
    assert core.tools.permission_gate.mode == AutonomyMode.EXECUTE_WITH_CONFIRMATION
    assert core.settings.get("autonomy.mode") == AutonomyMode.EXECUTE_WITH_CONFIRMATION.value
    panel.close(); core.context._memory.close(); core.context._knowledge.close()
