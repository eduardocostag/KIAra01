"""Exercise the actual Hunter component locally with intercepted API responses."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

URL = "http://localhost:3100/ui-verification"
JOB = {"id": "search-test", "market": "b2b", "query": "Clínicas de teste", "location": "São Paulo", "sources": ["google_maps"], "result_limit": 10, "website_filter": "without_website", "contact_filter": "whatsapp", "validation": {"checked": 3, "accepted": 1, "excluded": 2, "unknown": 1, "source_failures": 0}, "warnings": ["1 candidato excluído por falta de evidência."], "sync_summary": {"created": 1, "existing": 0, "skipped": 0}, "status": "completed", "results": [{"id": "lead-test", "source": "google_maps", "title": "Clínica de teste — evidência", "url": "https://www.google.com/maps/place/test", "summary": "Atendimento psicológico.", "public_data": {"phone": "+5511987654321", "whatsapp_url": "https://wa.me/5511987654321", "website_status": "not_listed", "website_evidence": "Campo Site não informado no perfil inspecionado.", "address": "São Paulo", "criterion_status": "verified", "lead_id": "lead-1", "pipeline_entry_id": "pipeline-1", "crm_status": "synced"}}]}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        state = {"mode": "success", "gets": 0, "confirms": 0}

        def route_api(route):
            request = route.request
            if request.method == "GET":
                state["gets"] += 1
                if state["mode"] == "broken_history":
                    route.fulfill(status=200, content_type="text/html", body="<html>Unexpected response</html>")
                else:
                    route.fulfill(json={"items": []})
            elif request.url.endswith("/confirm"):
                state["confirms"] += 1
                if state["mode"] == "broken_confirm":
                    route.fulfill(status=200, content_type="text/html", body="<html>Unexpected response</html>")
                elif state["mode"] == "network":
                    route.abort("failed")
                else:
                    result = {**JOB, "results": [] if state["mode"] == "empty" else JOB["results"]}
                    route.fulfill(json=result)
            else:
                route.fulfill(status=201, json={**JOB, "status": "pending_confirmation", "results": []})

        page.route("**/api/hunter/searches**", route_api)

        def run_search(mode):
            state["mode"] = mode
            page.goto(URL)
            expect(page.get_by_text("Nenhuma pesquisa registrada", exact=True)).to_be_visible()
            page.get_by_label("Quem você quer encontrar?").fill("Clínicas de teste")
            state["initial_gets"] = state["gets"]
            page.get_by_role("button", name="Revisar pesquisa", exact=True).click()
            page.get_by_role("button", name="Confirmar e pesquisar", exact=True).click()

        run_search("success")
        expect(page.get_by_role("heading", name="Pesquisa concluída: 1 resultado", exact=True)).to_be_visible()
        expect(page.get_by_role("article", name="Clínica de teste — evidência")).to_be_visible()
        expect(page.get_by_role("link", name="Abrir WhatsApp")).to_be_visible()
        expect(page.get_by_text("No pipeline", exact=True)).to_be_visible()
        assert state["gets"] == state["initial_gets"], "Result rendering must not depend on a second history request"
        assert state["confirms"] == 1
        panel_top = page.get_by_label("Acompanhamento e resultados da pesquisa").evaluate("el => el.getBoundingClientRect().top")
        assert 0 <= panel_top < 500, f"Results must be in the mobile viewport, top={panel_top}"
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile must not overflow"
        page.screenshot(path=str(Path(__file__).parent / "hunter-mobile-result.png"), full_page=True)
        print("PASS success: response rendered directly, mobile panel visible, no duplicate confirmation")

        run_search("empty")
        expect(page.get_by_role("heading", name="Nenhum resultado encontrado", exact=True)).to_be_visible()
        print("PASS empty: explicit no-results message")
        run_search("broken_confirm")
        expect(page.get_by_label("Acompanhamento e resultados da pesquisa").get_by_role("alert")).to_contain_text("não retornou os dados")
        print("PASS invalid response: visible error with recovery")
        run_search("network")
        expect(page.get_by_label("Acompanhamento e resultados da pesquisa").get_by_role("alert")).to_contain_text("Falha de conexão")
        print("PASS network error: visible error with recovery")
        state["mode"] = "broken_history"
        page.goto(URL)
        expect(page.get_by_label("Acompanhamento e resultados da pesquisa").get_by_role("alert")).to_be_visible()
        expect(page.get_by_text("Nenhuma pesquisa registrada", exact=True)).to_have_count(0)
        print("PASS invalid history: not disguised as empty state")
        assert not errors, json.dumps(errors)
        browser.close()


if __name__ == "__main__":
    main()
