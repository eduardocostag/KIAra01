"""Local UI contract check with fictional prospects and intercepted APIs."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={"width":1440,"height":1000})
    errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    def api(route):
        url=route.request.url
        if "/instagram/connection" in url:
            if route.request.method=="DELETE":route.fulfill(status=204)
            else:route.fulfill(json={"connected":True})
        elif "/overview" in url:
            route.fulfill(json={"analyses":{"items":[{"id":"test-analysis","name":"Análise de teste","status":"completed","prospect_count":2}]}})
        elif "/prospects" in url:
            route.fulfill(json={"items":[{"id":"1","username":"ana","email":"ana@example.test","profile_url":"https://www.instagram.com/ana/"},{"id":"2","username":"bia"}]})
        else:route.fulfill(status=500,json={"error":{"message":"Unexpected test request"}})
    page.route("**/api/competition/**",api)
    page.goto("http://localhost:3100/ui-verification?view=competition")
    page.get_by_role("button",name="Análise de teste",exact=False).click()
    expect(page.get_by_text("ana@example.test",exact=True)).to_be_visible()
    page.get_by_label("Somente com contato público").check()
    expect(page.get_by_text("1 de 2 perfis.",exact=False)).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role("button",name="Exportar CSV").click()
    csv=Path(download.value.path()).read_text(encoding="utf-8-sig")
    assert "ana@example.test" in csv and '"bia"' not in csv
    page.get_by_label("Buscar nesta análise").fill("inexistente")
    expect(page.get_by_role("button",name="Exportar CSV")).to_be_disabled()
    page.get_by_label("Buscar nesta análise").fill("")
    page.set_viewport_size({"width":390,"height":844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"),"Mobile overflow"
    page.screenshot(path=str(Path(__file__).parent/"competition-mobile.png"),full_page=True)
    assert not errors,errors
    print("PASS: archived results, public-contact filter, filtered CSV download, empty search, mobile width, no page errors")
    browser.close()
