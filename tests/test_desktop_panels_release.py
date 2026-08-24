from __future__ import annotations

import ast
import os
import threading
from pathlib import Path

import pytest

from app import autostart
from app.knowledge import KnowledgeStore
from app.memory import MemoryEngine, MemoryKind


def test_autostart_command_is_explicit_and_does_not_enable(monkeypatch) -> None:
    monkeypatch.setattr("sys.executable", r"C:\Program Files\Kiara\python.exe")
    command = autostart.command_for_current_install()
    assert command.startswith('"')
    assert command.endswith(" -m app")


def test_pyinstaller_spec_and_build_script_smoke() -> None:
    root = Path(__file__).parents[1]
    spec = root / "kiara.spec"
    ast.parse(spec.read_text(encoding="utf-8"))
    script = (root / "scripts" / "build-windows.ps1").read_text(encoding="utf-8")
    assert "PyInstaller" in script
    assert "pytest" in script and "ruff" in script
    assert "Get-AuthenticodeSignature" in script
    assert "SignatureStatus]::Valid" in script
    assert "KIARA_ALLOW_UNSIGNED_DEV_BUILD" in script
    assert "uac_admin=False" in spec.read_text(encoding="utf-8")


def test_panels_and_overlay_render_offscreen(monkeypatch) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from app.ui.overlay import StatusOverlay
    from app.ui.panels import InfoPanel, SettingsPanel

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("app.ui.panels.autostart.is_enabled", lambda: False)
    panel = InfoPanel(lambda: {"status": "ok"}, "vazio")
    settings = SettingsPanel(lambda: {"provider": "local"})
    overlay = StatusOverlay()
    try:
        assert '"status": "ok"' in panel.output.toPlainText()
        assert settings.autostart.isChecked() is False
        overlay.set_state("Pensando")
        overlay.show_discreetly()
        app.processEvents()
        assert overlay.isVisible()
        assert "pensando" in overlay.accessibleDescription().casefold()
    finally:
        overlay.close()
        settings.close()
        panel.close()


def test_panel_counts_use_independent_read_connections(tmp_path) -> None:
    memory = MemoryEngine(tmp_path / "memory.db")
    knowledge = KnowledgeStore(tmp_path / "knowledge.db")
    memory.remember(MemoryKind.SEMANTIC, "registro")
    document = tmp_path / "document.txt"
    document.write_text("conteúdo local", encoding="utf-8")
    knowledge.ingest(document)
    observed = []

    thread = threading.Thread(
        target=lambda: observed.append(
            (memory.count(), knowledge.document_count(), knowledge.chunk_count())
        )
    )
    thread.start()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert observed == [(1, 1, 1)]
    memory.close()
    knowledge.close()
