"""UI-only WhatsApp checks. All account/bridge APIs are intercepted; no messages are sent."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "evidence" / "whatsapp-module-2026-11-12"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
    state = {"connected": False, "deny": False, "analyzed": 0, "bad_analysis": False}
    errors = []
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))

    def session(route):
        route.fulfill(status=403 if state["deny"] else 200, json={"error": {"message": "Accès refusé"}} if state["deny"] else {"access_token": "ui-test-token", "expires_at": 9999999999})

    def bridge(route):
        assert route.request.headers.get("authorization") == "Bearer ui-test-token"
        headers = {"Access-Control-Allow-Origin": "http://localhost:3100", "Access-Control-Allow-Headers": "authorization,content-type", "Access-Control-Allow-Methods": "POST,OPTIONS"}
        if route.request.method == "OPTIONS":
            route.fulfill(status=204, headers=headers)
        elif route.request.url.endswith("/status"):
            route.fulfill(headers=headers, json={"connected": state["connected"], "phone": "+5511999999999" if state["connected"] else "", "model": "kiara-test:local"})
        else:
            state["analyzed"] += 1
            route.fulfill(headers=headers, json={"summary": None} if state["bad_analysis"] else {"summary": ("Resumo de teste. Pedido de orçamento e próximo passo para revisão humana.\n" * 18), "messages_analyzed": 12, "phone": "+5511999999999"})

    page.route("**/api/whatsapp-web/session", session)
    page.route("http://127.0.0.1:3007/**", bridge)
    page.goto("http://localhost:3100/ui-verification?workspace=gateway", wait_until="domcontentloaded", timeout=60000)
    expect(page.get_by_role("heading", name="Central do WhatsApp")).to_be_visible()
    expect(page.get_by_text("Conexão pendente", exact=True)).to_be_visible()
    page.evaluate("history.replaceState(null, '', '/app/whatsapp')")
    nav = page.locator("aside.kiara-sidebar nav")
    expect(nav.get_by_role("link", name="Visão geral", exact=True)).to_have_attribute("aria-current", "page")
    expect(page.get_by_role("button", name="Analisar conversa autorizada")).to_be_disabled()
    expect(page.get_by_role("link", name="Abrir WhatsApp local")).to_have_attribute("href", "http://127.0.0.1:3006")
    page.screenshot(path=str(OUT / "desktop-disconnected.png"), full_page=True)

    nav.get_by_role("link", name="Análise da conversa", exact=True).click()
    expect(nav.locator('[aria-current="page"]')).to_have_count(1)
    expect(nav.get_by_role("link", name="Análise da conversa", exact=True)).to_have_attribute("aria-current", "page")
    state["connected"] = True
    page.get_by_role("button", name="Atualizar conexão", exact=True).click()
    button = page.get_by_role("button", name="Analisar conversa autorizada")
    expect(button).to_be_enabled()
    page.evaluate("window.scrollTo(0,0)")
    page.screenshot(path=str(OUT / "desktop-connected.png"), full_page=True)
    button.click()
    expect(page.get_by_text("12 mensagens · +5511999999999")).to_be_visible()
    page.screenshot(path=str(OUT / "desktop-analysis.png"), full_page=True)
    assert state["analyzed"] == 1

    state["bad_analysis"] = True
    page.get_by_role("button", name="Analisar novamente").click()
    expect(page.locator("main").get_by_role("alert")).to_contain_text("resumo válido")
    state["deny"] = True
    page.get_by_role("button", name="Atualizar conexão", exact=True).click()
    expect(page.locator("main").get_by_role("alert")).to_contain_text("autorização")
    expect(page.get_by_role("button", name="Analisar conversa autorizada")).to_be_disabled()

    page.set_viewport_size({"width": 390, "height": 844})
    page.evaluate("window.scrollTo(0,0)")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile overflow"
    page.screenshot(path=str(OUT / "mobile-disconnected.png"), full_page=True)
    page.get_by_role("button", name="Abrir menu", exact=True).click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_role("link", name="Automação e contatos", exact=True)).to_be_visible()
    page.screenshot(path=str(OUT / "mobile-sidebar.png"), full_page=True)
    dialog.get_by_role("link", name="Configuração local", exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.locator("#configuracoes")).to_have_attribute("open", "")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors, errors
    (OUT / "browser-result.json").write_text(json.dumps({"passed": True, "mode": "intercepted_apis_no_account_or_messages", "checks": ["disconnected", "connected", "analysis", "invalid_response", "access_denied", "sidebar_hash", "mobile_menu", "mobile_width", "no_page_errors"], "screenshots": 5}, indent=2), encoding="utf-8")
    print("PASS: WhatsApp module states, analysis, permissions, sidebar and mobile; no real account access or messages")
    browser.close()

