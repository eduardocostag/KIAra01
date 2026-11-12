"""Exercise WhatsApp automation with intercepted APIs and no real sends.

Requires the development-only /ui-verification harness on localhost:3100.
"""
import copy
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "evidence/whatsapp-module-2026-11-12"
OUTPUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors, sent, unexpected = [], [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    config = {
        "pilot_mode": False, "pilot_consent_confirmed": False, "enabled": False,
        "daily_limit": 25, "auto_reply_enabled": True, "followup_enabled": False,
        "initial_outreach_enabled": False, "outreach_template": "", "ai_context": "",
        "reply_template": "Olá {name}, vou chamar uma pessoa.",
        "followup_template": "Olá {name}, posso ajudar?", "followup_hours": 48,
        "contact_start": "09:00", "contact_end": "18:00", "contacts": [],
    }
    polls = [0]

    def api(route):
        if route.request.url.endswith("/whatsapp-web/config"):
            if route.request.method == "PUT":
                payload = route.request.post_data_json
                sent.append(copy.deepcopy(payload))
                config.update(copy.deepcopy(payload))
            route.fulfill(json=config)
        elif route.request.url.endswith("/whatsapp-web/events"):
            polls[0] += 1
            route.fulfill(json={
                "items": [{"id": "e1", "phone": "5511999999999", "kind": "inbound", "text": "Mensagem de teste", "occurred_at": "2026-11-12T12:00:00Z", "status": "recorded"}],
                "last_heartbeat_at": "2026-11-12T12:00:00Z", "online": True,
            })
        else:
            unexpected.append(route.request.url)
            route.fulfill(status=503, json={"error": {"message": "Requisição bloqueada pelo teste."}})

    page.route("**/api/**", api)
    page.goto("http://localhost:3100/ui-verification", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Automação e contatos", exact=True)).to_be_visible()
    page.evaluate("window.history.replaceState({}, '', '/app/whatsapp/automacao')")
    expect(page.get_by_text("Mensagem de teste", exact=True)).to_be_visible()
    expect(page.get_by_text("Automação pausada", exact=True)).to_be_visible()
    expect(page.get_by_text("Conexão do executor · extensão Chrome", exact=True)).to_be_visible()

    page.get_by_text("Adicionar contato manualmente", exact=True).click()
    page.get_by_label("Nome", exact=True).fill("Contato de teste")
    page.get_by_label("Telefone com DDI e DDD").fill("+55 (11) 99999-9999")
    page.get_by_role("button", name="Adicionar contato", exact=True).click()
    enabled = page.get_by_label("Habilitar a operação autônoma", exact=True)
    consent = page.get_by_label("Confirmo que os contatos selecionados estão autorizados", exact=False)
    save = page.get_by_role("button", name="Salvar automação do WhatsApp", exact=True)

    enabled.check()
    save.click()
    expect(page.locator("section[aria-labelledby='whatsapp-heading']").get_by_role("alert")).to_contain_text("confirme a ativação")
    assert not sent, "Activation bypassed missing consent"
    consent.check()
    save.click()
    expect(page.locator("section[aria-labelledby='whatsapp-heading']").get_by_role("alert")).to_contain_text("informações autorizadas da empresa")
    assert not sent, "Activation bypassed missing approved business context"
    page.get_by_label("Informações autorizadas para a IA", exact=True).fill("Empresa de teste. Atendimento das 9h às 18h. Encaminhe dúvidas não previstas a uma pessoa.")
    save.click()
    expect(page.get_by_text("Automação ativa", exact=True)).to_be_visible()
    assert sent[-1]["contacts"] == [{"phone": "5511999999999", "name": "Contato de teste", "enabled": True, "handoff": False}]

    page.get_by_label("Nome", exact=True).fill("Segundo contato de teste")
    page.get_by_label("Telefone com DDI e DDD").fill("5511988888888")
    page.get_by_role("button", name="Adicionar contato", exact=True).click()
    expect(enabled).not_to_be_checked()
    expect(consent).not_to_be_checked()
    enabled.check()
    consent.check()
    save.click()
    expect(save).to_be_enabled()
    assert len(sent[-1]["contacts"]) == 2

    page.get_by_label("Atendimento humano para Contato de teste", exact=True).check()
    save.click()
    expect(save).to_be_enabled()
    assert sent[-1]["contacts"][0]["handoff"] is True
    assert sent[-1]["contacts"][1]["enabled"] is True
    assert sent[-1]["enabled"] is True

    before = polls[0]
    page.get_by_label("Mensagem de follow-up", exact=True).fill("Edição ainda não salva")
    page.wait_for_timeout(11000)
    assert polls[0] > before, "Activity polling did not execute"
    expect(page.get_by_label("Mensagem de follow-up", exact=True)).to_have_value("Edição ainda não salva")
    page.get_by_label("Follow-up após (horas)", exact=True).fill("0")
    page.get_by_role("button", name="Pausar automação", exact=True).click()
    expect(page.get_by_text("Automação pausada", exact=True)).to_be_visible()
    assert sent[-1]["enabled"] is False
    assert sent[-1]["followup_hours"] == 48, "Pause persisted an invalid unsaved hour limit"
    assert sent[-1]["followup_template"] != "Edição ainda não salva", "Pause persisted an unrelated unsaved edit"
    assert sent[-1]["contacts"][0]["handoff"] is True

    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(OUTPUT / "automation-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Horizontal mobile overflow"
    page.screenshot(path=str(OUTPUT / "automation-mobile.png"), full_page=True)
    assert not errors, errors
    assert not unexpected, unexpected
    report = {
        "mode": "mocked_browser_no_real_messages", "passed": True,
        "checks": ["contact registration", "activation requires consent", "activation requires business context", "save and enable", "new contacts reset activation and consent", "human handoff persists", "polling preserves edits", "pause ignores invalid unsaved edits", "mobile width", "no page errors", "no unexpected API calls"],
        "config_writes_intercepted": len(sent), "event_polls_intercepted": polls[0],
        "screenshots": ["automation-desktop.png", "automation-mobile.png"],
    }
    (OUTPUT / "automation-browser-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    browser.close()
