"""Check WhatsApp UI with synthetic browser responses; never contacts WhatsApp."""
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence" / "whatsapp-simplified"


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = {
        "enabled": True, "pilot_mode": True, "daily_limit": 50,
        "pilot_consent_confirmed": True, "auto_reply_enabled": True,
        "followup_enabled": False, "initial_outreach_enabled": False,
        "ai_context": "Empresa de teste. Plano aprovado: R$ 149.",
        "reply_template": "Vou chamar uma pessoa.", "followup_template": "Posso ajudar?",
        "followup_hours": 48, "contact_start": "09:00", "contact_end": "18:00",
        "contacts": [{"phone": "5511999999999", "name": "Contato fictício", "enabled": True, "handoff": False}],
    }
    sent = []

    def mock_api(route):
        if route.request.url.endswith("/config"):
            if route.request.method == "PUT":
                sent.append(route.request.post_data_json)
                config.update(route.request.post_data_json)
            route.fulfill(json=config)
        elif route.request.url.endswith("/events"):
            route.fulfill(json={"online": False, "last_heartbeat_at": None, "items": [
                {"id": "h1", "phone": "", "kind": "heartbeat", "text": "ready", "status": "ready", "occurred_at": "2026-11-10T12:00:00Z"},
                {"id": "m1", "phone": "5511999999999", "kind": "inbound", "text": "Mensagem fictícia de validação", "status": "recorded", "occurred_at": "2026-11-10T12:01:00Z"},
            ]})
        else:
            route.fulfill(status=503, json={"error": {"message": "Serviço de teste indisponível"}})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.add_init_script("""window.open = () => null;
          window.addEventListener('message', event => {
            if (event.data?.source === 'kiara-app' && event.data.type === 'whatsapp-prepare') {
              window.postMessage({source: 'kiara-whatsapp-extension', type: 'whatsapp-ready',
                requestId: event.data.requestId, error: 'Extensão de teste indisponível.'}, location.origin)
            }
          });""")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/api/whatsapp-web/**", mock_api)
        page.goto("http://127.0.0.1:3100/ui-verification", wait_until="networkidle")
        expect(page.locator("#wa-ai-context")).not_to_be_visible()
        expect(page.get_by_text("Mensagem fictícia de validação", exact=True)).not_to_be_visible()
        expect(page.get_by_role("button", name="Pausar automação")).to_be_visible()
        page.screenshot(path=str(OUTPUT / "desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile overflow"
        page.screenshot(path=str(OUTPUT / "mobile.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.locator("summary").filter(has_text="Histórico do atendimento").click()
        expect(page.get_by_text("Mensagem fictícia de validação", exact=True)).to_be_visible()
        expect(page.get_by_text("ready", exact=True)).to_have_count(0)
        page.locator("summary").filter(has_text="Histórico do atendimento").click()
        page.locator("summary").filter(has_text="Configurações").first.click()
        expect(page.locator("#wa-ai-context")).to_be_visible()
        page.locator("#wa-followup").fill("0")
        page.get_by_role("button", name="Pausar automação").first.click()
        expect(page.get_by_role("button", name="Pausar automação")).to_have_count(0)
        assert sent[-1]["enabled"] is False
        assert sent[-1]["followup_hours"] == 48, "Pause persisted invalid unsaved settings"
        page.locator("#wa-followup").fill("0")
        page.get_by_role("button", name="Salvar automação do WhatsApp").click()
        expect(page.get_by_role("alert").filter(has_text="prazo")).to_be_visible()
        expect(page.get_by_role("button", name="Analisar conversas", exact=True)).to_be_visible()
        page.get_by_role("button", name="Analisar conversas", exact=True).click()
        expect(page.get_by_role("button", name="Tentar novamente", exact=True)).to_be_visible()
        expect(page.get_by_text("Extensão de teste indisponível.", exact=True)).to_be_visible()
        expect(page.get_by_text("Conectando automaticamente", exact=False)).to_have_count(0)
        page.locator("summary").filter(has_text="Configurações").first.click()
        page.screenshot(path=str(OUTPUT / "connection-error.png"), full_page=True)
        assert not errors, errors
        browser.close()
    print("PASS: collapsed settings, visible pause, mobile width, pause preserves saved settings, no browser errors")


if __name__ == "__main__":
    main()
