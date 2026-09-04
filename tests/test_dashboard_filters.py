from __future__ import annotations

import os
from datetime import UTC

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_legacy_timestamps_are_normalized_and_missing_readiness_stays_unknown():
    pytest.importorskip("PySide6")
    from app.ui.desktop import KiaraWindow

    assert KiaraWindow._utc_datetime("2026-09-04T10:30:00").tzinfo is UTC
    assert KiaraWindow._readiness_score({}) is None
    assert KiaraWindow._readiness_score({"readiness_score": "invalid"}) is None
    assert KiaraWindow._readiness_score({"readiness_score": 0}) == 0
    assert KiaraWindow._readiness_score({"readiness_score": 120}) == 100


def test_dashboard_filter_updates_kpis_table_kanban_and_charts(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from app.leads import LeadStage, LeadStore
    from app.ui.desktop import KiaraWindow

    store = LeadStore(tmp_path / "leads.db")
    first = store.upsert(
        company="Clínica Aurora", niche="Estética", location="Porto Alegre",
        source_url="https://www.google.com/maps/place/aurora", score=80,
    )
    second = store.upsert(
        company="Studio Nexo", niche="Estética", location="Canoas",
        source_url="https://www.instagram.com/studionexo", score=72,
    )
    store.update(second, stage=LeadStage.QUALIFIED)

    class Settings:
        root = tmp_path

        @staticmethod
        def get(_key, default=None):
            return default

    class Core:
        lead_store = store
        consumer_store = None
        settings = Settings()

        def start_background(self):
            return None

        def stop_background(self):
            return None

        async def handle(self, message):
            return message

    class Kill:
        def trigger(self):
            return None

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("app.ui.desktop.QSystemTrayIcon.isSystemTrayAvailable", lambda: False)
    window = KiaraWindow(Core(), Kill())
    try:
        window.cockpit.period_filter.setCurrentIndex(3)
        qualified_index = window.cockpit.stage_filter.findData("qualificados")
        window.cockpit.stage_filter.setCurrentIndex(qualified_index)
        app.processEvents()

        assert [lead.id for lead in window._visible_leads] == [second]
        assert window.cockpit.opportunity_table.rowCount() == 1
        assert window.cockpit.pipeline_counts["qualificados"].text() == "1"
        assert window.cockpit.pipeline_counts["descobertos"].text() == "0"
        assert window.cockpit.performance_chart._values[-1] == 1
        assert window.cockpit.funnel_donut._values == (0, 1, 0, 0, 0, 0)
        source_row = window.cockpit.sources_layout.itemAt(0).layout()
        assert source_row is not None
        assert source_row.itemAt(0).widget().text() == "Instagram"
        assert source_row.itemAt(3).widget().text() == "1"
        assert first not in {lead.id for lead in window._visible_leads}
    finally:
        window.shutdown()
        window.deleteLater()
        store.close()
