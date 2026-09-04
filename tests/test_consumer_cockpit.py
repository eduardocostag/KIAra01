import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_consumer_cockpit_renders_consent_and_customer_room() -> None:
    from PySide6.QtWidgets import QApplication

    from app.ui.consumer_cockpit import (
        ConsumerCockpit,
        ConsumerSummary,
        CustomerDetail,
    )

    app = QApplication.instance() or QApplication([])
    cockpit = ConsumerCockpit()
    assert all(section.isHidden() for section in cockpit.room._sections)
    assert cockpit.list_stack.currentIndex() == 0
    cockpit.set_consumers((
        ConsumerSummary("p1", "Ana", "Instagram", 82, "Pronto", "Válido", "Agendar"),
    ))
    cockpit.set_customer_detail(CustomerDetail(
        "p1", "Ana", "Pronto para comprar", 82, "Instagram · campanha verão",
        "Quer reduzir tempo de atendimento", ("Pediu preço", "Respondeu à DM"),
        "Consentimento válido", ("instagram",), ("Prazo exato",),
        recommended_offer="Plano Pro", suggested_message="Posso reservar um horário?",
        next_action="Agendar conversa",
    ))
    app.processEvents()

    assert cockpit.table.rowCount() == 1
    assert cockpit.list_stack.currentIndex() == 1
    assert cockpit.room.readiness.text() == "PRONTO PARA COMPRAR"
    assert "instagram" in cockpit.room.consent.text()
    assert cockpit.action.isEnabled()
    assert all(not section.isHidden() for section in cockpit.room._sections)


def test_consumer_action_stays_blocked_without_allowed_channel() -> None:
    from PySide6.QtWidgets import QApplication

    from app.ui.consumer_cockpit import ConsumerCockpit, CustomerDetail

    QApplication.instance() or QApplication([])
    cockpit = ConsumerCockpit()
    cockpit.set_customer_detail(CustomerDetail("p2", "Pessoa", next_action="Contatar"))

    assert not cockpit.action.isEnabled()


def test_desktop_connects_consumer_store_to_b2c_workspace(tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication

    from app.consumers import ConsumerStore
    from app.ui.desktop import KiaraWindow

    class Core:
        def __init__(self, store):
            self.consumer_store = store
            self.settings = SimpleNamespace(root=tmp_path, get=lambda _key, default=None: default)

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
    store = ConsumerStore(tmp_path / "consumers.db")
    person_id = store.upsert_person(
        display_name="Ana", platform="instagram", scoped_id="ig-ana", source="meta"
    )
    store.record_consent(
        person_id, channel="instagram_dm", purpose="vendas", source="lead_form"
    )
    store.add_touchpoint(person_id, platform="instagram", kind="price_request", direction="inbound")
    monkeypatch.setattr("app.ui.desktop.QSystemTrayIcon.isSystemTrayAvailable", lambda: False)
    window = KiaraWindow(Core(store), Kill())
    try:
        window._open_consumers()
        window.consumer_cockpit.table.selectRow(0)
        app.processEvents()
        assert window.workspace_stack.currentIndex() == 2
        assert window.consumer_cockpit.table.item(0, 0).text() == "Ana"
        assert "instagram" in window.consumer_cockpit.room.origin.text().casefold()
        assert "consentimento válido" in window.consumer_cockpit.room.consent.text().casefold()
    finally:
        window.shutdown()
        window.deleteLater()
