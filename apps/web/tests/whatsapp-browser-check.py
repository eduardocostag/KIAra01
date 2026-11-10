"""Browser UI checks with intercepted APIs; never connects to WhatsApp.
Requires temporary /ui-verification page rendering WhatsAppWebWorkspace at :3100.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors, sent = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    config = {"enabled": False, "reply_template": "Olá {name}, vou chamar uma pessoa.", "followup_template": "Olá {name}, posso ajudar?", "followup_hours": 48, "contact_start": "09:00", "contact_end": "18:00", "contacts": []}
    polls = [0]
    def api(route):
        if route.request.url.endswith("/config"):
            if route.request.method == "PUT":
                sent.append(route.request.post_data_json)
                config.update(route.request.post_data_json)
            route.fulfill(json=config)
        elif route.request.url.endswith("/events"):
            polls[0] += 1
            route.fulfill(json={"items": [{"id": "e1", "phone": "5511999999999", "kind": "inbound", "text": "Mensagem de teste", "occurred_at": "2026-10-13T12:00:00Z", "status": "recorded"}], "last_heartbeat_at": "2026-10-13T12:00:00Z", "online": True})
        else:
            route.fulfill(status=500, json={"error": {"message": "Unexpected test request"}})
    page.route("**/api/whatsapp-web/**", api)
    page.goto("http://localhost:3100/ui-verification")
    expect(page.get_by_text("Mensagem de teste", exact=True)).to_be_visible()
    expect(page.get_by_text("Automação pausada", exact=True)).to_be_visible()
    page.get_by_label("Nome", exact=True).fill("Contato de teste")
    page.get_by_label("Telefone com DDI e DDD").fill("+55 (11) 99999-9999")
    page.get_by_role("button", name="Adicionar contato").click()
    page.get_by_label("Habilitar atendimento automático ao salvar").check()
    page.get_by_role("button", name="Salvar automação do WhatsApp").click()
    expect(page.get_by_text("Automação habilitada", exact=True)).to_be_visible()
    assert sent[-1]["contacts"] == [{"phone": "5511999999999", "name": "Contato de teste", "enabled": True, "handoff": False}]
    page.get_by_label("Atendimento humano para Contato de teste").check()
    page.get_by_role("button", name="Salvar automação do WhatsApp").click()
    expect(page.get_by_role("button", name="Salvar automação do WhatsApp")).to_be_enabled()
    assert sent[-1]["contacts"][0]["handoff"] is True
    before = polls[0]
    page.get_by_label("Mensagem de follow-up", exact=True).fill("Edição ainda não salva")
    page.wait_for_timeout(11000)
    assert polls[0] > before, "History polling did not execute"
    expect(page.get_by_label("Mensagem de follow-up", exact=True)).to_have_value("Edição ainda não salva")
    page.get_by_label("Follow-up após (horas)").fill("0")
    page.get_by_role("button", name="Pausar automação").click()
    expect(page.get_by_text("Automação pausada", exact=True)).to_be_visible()
    assert sent[-1]["enabled"] is False
    assert sent[-1]["followup_hours"] == 48, "Pause persisted invalid unsaved edit"
    assert sent[-1]["followup_template"] != "Edição ainda não salva"
    page.screenshot(path=str(Path(__file__).parent / "whatsapp-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Horizontal mobile overflow"
    page.screenshot(path=str(Path(__file__).parent / "whatsapp-mobile.png"), full_page=True)
    assert not errors, errors
    print("PASS: contact registration, save/enable, handoff, polling preserves edit, pause ignores unsaved invalid data, mobile width, no page errors")
    browser.close()
