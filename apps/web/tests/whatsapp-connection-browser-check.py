"""Connection UI checks with synthetic QR and extension responses, no account access."""
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

OUT = Path(__file__).resolve().parents[3] / "evidence" / "whatsapp-connection-fix"
OUT.mkdir(parents=True, exist_ok=True)
PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1cAAAAASUVORK5CYII="

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    state = {"connected": False, "pairs": 0, "extension": False}

    def api(route):
        if route.request.url.endswith("/session"):
            route.fulfill(json={"access_token": "connection-ui-test", "expires_at": 9999999999})
        elif route.request.url.endswith("/events"):
            route.fulfill(json={"online": state["extension"], "last_heartbeat_at": None, "items": []})
        else:
            route.fulfill(status=500, json={"error": {"message": "Unexpected test request"}})

    def bridge(route):
        headers = {"Access-Control-Allow-Origin": "http://localhost:3100", "Access-Control-Allow-Headers": "authorization,content-type", "Access-Control-Allow-Methods": "POST,OPTIONS"}
        if route.request.method == "OPTIONS":
            route.fulfill(status=204, headers=headers)
        elif route.request.url.endswith("/status"):
            route.fulfill(headers=headers, json={"connected": state["connected"], "state": "ready" if state["connected"] else "created", "phone": "", "model": "test"})
        elif route.request.url.endswith("/connect"):
            state["pairs"] += 1
            state["connected"] = state["pairs"] > 1
            route.fulfill(headers=headers, json={"connected": state["connected"], "state": "ready" if state["connected"] else "qr_ready", "qr": "" if state["connected"] else PNG})
        else:
            raise AssertionError("This test must not read messages or start analysis")

    page.add_init_script("""
      document.addEventListener('click', e => {
        if (e.target.closest?.('a[href^="kiara-whatsapp:"]')) e.preventDefault();
      }, true);
      window.addEventListener('message', e => {
        if (e.data?.source === 'kiara-app' && e.data.type === 'whatsapp-prepare') {
          setTimeout(() => window.postMessage({source:'kiara-whatsapp-extension', type:'whatsapp-ready', requestId:e.data.requestId, error:null}, location.origin), 40);
        }
      });
    """)
    page.route("**/api/whatsapp-web/**", api)
    page.route("http://127.0.0.1:3009/**", bridge)
    page.goto("http://localhost:3100/ui-verification?workspace=whatsapp&view=empty", wait_until="domcontentloaded")
    page.get_by_role("button", name="Conexão", exact=True).first.click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_role("button", name="Conectar WhatsApp", exact=True)).to_be_enabled()
    dialog.get_by_role("button", name="Conectar WhatsApp", exact=True).click()
    expect(dialog.get_by_role("img", name="QR Code para conectar o WhatsApp")).to_be_visible()
    page.screenshot(path=str(OUT / "synthetic-qr.png"))
    expect(dialog.get_by_text("Tudo certo. Você pode fechar esta janela.", exact=True)).to_be_visible(timeout=15000)
    dialog.get_by_text("Outra forma: extensão do Chrome (opcional)", exact=True).click()
    state["extension"] = True
    dialog.get_by_role("button", name="Conectar pela extensão", exact=True).click()
    expect(dialog.get_by_text("Extensão conectada", exact=True)).to_be_visible()
    expect(dialog.get_by_role("link", name="Baixe a extensão")).not_to_be_visible()
    dialog.get_by_text("Instalar ou atualizar a extensão Kiara", exact=True).click()
    expect(dialog.get_by_role("link", name="Baixe a extensão")).to_have_attribute("href", "/downloads/kiara-whatsapp-extension.zip")
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(OUT / "connection-mobile.png"))
    assert not errors, errors
    print("PASS: synthetic QR polling and confirmation, optional extension handshake, download and mobile width; no real account access or messages")
    browser.close()
