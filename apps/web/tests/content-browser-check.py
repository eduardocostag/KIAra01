"""Real components with intercepted APIs; does not publish to any social network.
Requires a temporary /ui-verification page rendering ContentWorkspace on port 3100.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    sent = []
    draft = {"id":"draft-1", "content":"Legenda original", "status":"draft", "version":3, "created_at":"2026-09-30T12:00:00Z", "targets":[{"channel_id":"channel-1","channel_name":"Canal local","provider":"threads"}], "media":[]}
    def api(route):
        request = route.request
        path = request.url.split("?")[0]
        if "/postiz/dashboard" in path:
            route.fulfill(json={"integrations":[{"id":"remote-1","name":"Canal conectado","identifier":"threads"},{"id":"tiktok-1","name":"TikTok teste","identifier":"tiktok"}],"posts":[]})
        elif path.endswith("/postiz/upload"):
            route.fulfill(status=201,json={"id":"media-1","path":"https://uploads.example.test/test.mp4"})
        elif "/postiz/analytics/" in path:
            route.fulfill(json=[{"label":"Followers","data":[{"total":"12","date":"2026-09-30"}]}])
        elif path.endswith("/postiz/posts"):
            sent.append((request.method,request.post_data_json,request.headers))
            route.fulfill(status=201,json=[{"postId":"remote-post"}])
        elif path.endswith("/content/dashboard"):
            route.fulfill(json={"channels":[{"id":"channel-1","name":"Canal local","provider":"threads"}],"posts":[draft]})
        elif path.endswith("/posts/draft-1") and request.method == "PUT":
            sent.append((request.method,request.post_data_json,request.headers))
            draft["content"] = request.post_data_json["content"]
            draft["version"] += 1
            route.fulfill(json=draft)
        else:
            route.fulfill(status=500,json={"error":{"message":"Unexpected test request"}})
    page.route("**/api/content/**",api)
    page.goto("http://127.0.0.1:3100/ui-verification?view=content")
    page.get_by_role("button",name="Criar publicação",exact=True).click()
    expect(page.get_by_label("Canal conectado")).to_have_value("remote-1")
    page.get_by_label("Legenda",exact=True).fill("Publicação de teste")
    page.get_by_label("Ação",exact=True).select_option("schedule")
    page.get_by_label("Data e hora local").fill("2099-10-01T12:00")
    page.get_by_role("button",name="Agendar publicação",exact=True).click()
    expect(page.get_by_text("Agendamento enviado ao Postiz.",exact=False)).to_be_visible()
    assert sent[-1][1]["type"] == "schedule"
    assert sent[-1][1]["integrationId"] == "remote-1"
    page.get_by_label("Canal conectado").select_option("tiktok-1")
    page.get_by_label("Legenda",exact=True).fill("Vídeo de teste")
    page.get_by_label("Mídia (até 4 MB por arquivo)").set_input_files({"name":"test.mp4","mimeType":"video/mp4","buffer":b"fixture"})
    expect(page.get_by_text("test.mp4",exact=True)).to_be_visible()
    page.get_by_label("Quem pode assistir?").select_option("SELF_ONLY")
    page.locator("summary").filter(has_text="Opções do TikTok").click()
    page.get_by_label("Vídeo gerado com IA").check()
    page.get_by_role("button",name="Agendar publicação",exact=True).click()
    expect(page.get_by_text("Agendamento enviado ao Postiz.",exact=False)).to_be_visible()
    assert sent[-1][1]["settings"]["content_posting_method"] == "DIRECT_POST"
    assert sent[-1][1]["settings"]["privacy_level"] == "SELF_ONLY"
    assert sent[-1][1]["settings"]["video_made_with_ai"] is True
    page.get_by_label("Canal conectado").select_option("remote-1")
    page.locator("summary").filter(has_text="Métricas dos canais").click()
    page.get_by_role("button",name="Consultar métricas").click()
    expect(page.get_by_text("Followers",exact=True)).to_be_visible()
    page.screenshot(path=str(Path(__file__).parent/"content-postiz-desktop.png"),full_page=True)
    page.get_by_role("tab",name="Preparar conteúdo",exact=True).click()
    page.get_by_role("button",name="Editar",exact=True).click()
    expect(page.get_by_label("Legenda",exact=True)).to_have_value("Legenda original")
    page.get_by_label("Legenda",exact=True).fill("Legenda revisada")
    page.get_by_role("button",name="Salvar rascunho",exact=True).click()
    expect(page.get_by_text("Legenda revisada",exact=True)).to_be_visible()
    assert sent[-1][0] == "PUT"
    assert sent[-1][2]["if-match"] == '\"3\"'
    assert len([entry for entry in sent if entry[0] == "PUT"]) == 1
    page.set_viewport_size({"width":390,"height":844})
    page.get_by_role("tab",name="Publicar e agendar",exact=True).click()
    page.get_by_role("button",name="Criar publicação",exact=True).click()
    expect(page.get_by_label("Canal conectado")).to_have_value("remote-1")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Horizontal mobile overflow"
    page.screenshot(path=str(Path(__file__).parent/"content-postiz-mobile.png"),full_page=True)
    assert not errors,errors
    print("PASS: schedule payload, analytics, draft PUT/If-Match without duplication, mobile width, no page errors")
    browser.close()
