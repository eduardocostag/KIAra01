"""Capture real Kiara screens (1920x1080) from the development preview, with demo data.

Requires `npx next dev -p 3100` in apps/web. APIs are mocked: no real customer data,
no messages sent. Output: assets/shots/<name>.png
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
SHOTS = ROOT / "assets" / "shots"
BASE = "http://localhost:3100"
PREVIEW = f"{BASE}/ui-verification"
HIDE_DEV = "nextjs-portal, [data-nextjs-toast], [data-next-badge-root] { display: none !important; }"


def result(i, name, phone, address, rating):
    return {"id": f"r{i}", "source": "google_maps", "title": name, "url": f"https://maps.google.com/?cid={i}",
            "summary": "Clínica odontológica com atendimento particular e convênios.",
            "public_data": {"phone": phone, "address": address, "detail_inspected": True, "website_status": "not_listed",
                            "rating": rating, "user_rating_count": 40 + i * 13, "lead_requirements_missing": []}}


HUNTER_JOB = {"id": "job-1", "market": "b2b", "query": "Dentistas sem site", "location": "Porto Alegre", "sources": ["google_maps", "web"],
              "result_limit": 10, "status": "completed",
              "validation": {"checked": 18, "accepted": 5, "excluded": 12, "unknown": 1, "incomplete": 0, "source_failures": 0},
              "results": [result(1, "Clínica Sorriso Vivo", "(51) 3333-1001", "Av. Ipiranga, 1200 · Porto Alegre, RS", 4.8),
                          result(2, "Odonto Centro POA", "(51) 99999-2002", "Rua dos Andradas, 845 · Porto Alegre, RS", 4.6),
                          result(3, "Instituto Dental Moinhos", "(51) 3333-3003", "Rua Padre Chagas, 210 · Porto Alegre, RS", 4.9),
                          result(4, "Sorria Mais Zona Sul", "(51) 99999-4004", "Av. Wenceslau Escobar, 1500 · Porto Alegre, RS", 4.7),
                          result(5, "Dental Point Cidade Baixa", "(51) 3333-5005", "Rua da República, 77 · Porto Alegre, RS", 4.5)]}

STATUS = {"connected": True, "provider": "omniroute", "model": "auto/best-chat", "capabilities": [
    {"id": "chat", "available": True, "detail": "Pronto"}, {"id": "speech", "available": False, "detail": "-"},
    {"id": "transcribe", "available": False, "detail": "-"}, {"id": "website", "available": True, "detail": "Pronto"}]}
CHAT_REPLY = {"text": "Aqui estão as prioridades de hoje:\n\n1. Enviar a proposta para a Clínica Sorriso Vivo — ela pediu valores ontem.\n2. Fazer o follow-up com a Dra. Marina Lopes, que está com a ação atrasada.\n3. Primeira abordagem à Odonto Centro POA pelo WhatsApp.\n4. Nova busca: dentistas sem site em Canoas.\n\nQuer que eu escreva a mensagem da proposta?"}

WA_CONFIG = {"pilot_mode": False, "daily_limit": 40, "auto_reply_enabled": True, "followup_enabled": True, "initial_outreach_enabled": True,
             "outreach_template": "Olá {name}, tudo bem? Vi que vocês ainda não têm um site com agenda online. Posso te mostrar um exemplo?",
             "pilot_consent_confirmed": True, "enabled": True,
             "ai_context": "Criamos sites profissionais para clínicas, com agendamento online pelo WhatsApp. Plano mensal a partir de R$ 189, com domínio e suporte. Atendimento de segunda a sexta, das 9h às 18h.",
             "reply_template": "Olá {name}, vou chamar uma pessoa da equipe para te ajudar.", "followup_template": "Olá {name}, conseguiu ver a proposta?",
             "followup_hours": 48, "contact_start": "09:00", "contact_end": "18:00",
             "contacts": [{"phone": "5551999990001", "name": "Clínica Sorriso Vivo", "enabled": True, "handoff": False},
                          {"phone": "5551999990002", "name": "Odonto Centro POA", "enabled": True, "handoff": False},
                          {"phone": "5551999990003", "name": "Dra. Marina Lopes", "enabled": True, "handoff": True}]}
WA_EVENTS = {"items": [{"id": "e1", "phone": "5551999990001", "kind": "reply", "text": "O plano mensal custa R$ 189 e inclui domínio e suporte.", "occurred_at": "2026-11-12T12:13:00Z", "status": "confirmed"}],
             "last_heartbeat_at": "2026-11-12T12:20:00Z", "online": True}
LEADS = {"items": [
    {"id": "e1", "stage": "opportunity", "next_action": "Enviar proposta", "version": 1, "updated_at": "2026-11-12T10:00:00Z", "consumer": {"id": "c1", "display_name": "Clínica Sorriso Vivo", "instagram_username": None, "phone": "(51) 99999-0001"}},
    {"id": "e2", "stage": "new", "next_action": None, "version": 1, "updated_at": "2026-11-12T09:00:00Z", "consumer": {"id": "c2", "display_name": "Odonto Centro POA", "instagram_username": None, "phone": "(51) 99999-0002"}},
]}
AUTOMATION_REPLY = {"text": "1. Enviar a proposta para a Clínica Sorriso Vivo hoje.\n2. Primeira abordagem à Odonto Centro POA.\n3. Revisar os leads novos de Porto Alegre."}
FAKE_VOICE = """
class FakeRecognition { constructor(){ this.onresult=null; this.onend=null; this.onerror=null; }
  start(){ window.__starts=(window.__starts||0)+1; if (window.__starts>1) return;
    setTimeout(()=>{ this.onresult&&this.onresult({resultIndex:0,results:[{isFinal:true,0:{transcript:'Kiara, o que eu priorizo hoje?'}}]}); this.onend&&this.onend(); }, 900); }
  abort(){ this.onend&&this.onend(); } }
window.webkitSpeechRecognition = FakeRecognition; window.SpeechRecognition = FakeRecognition;
window.speechSynthesis.speak = (u) => { let n=0; const t=setInterval(()=>{ u.onboundary&&u.onboundary({}); if(++n>200){clearInterval(t); u.onend&&u.onend();} }, 140); };
"""


def json_route(page, pattern, body, status=200):
    page.route(pattern, lambda route: route.fulfill(status=status, content_type="application/json", body=json.dumps(body)))


def settle(page, ms=1500):
    page.add_style_tag(content=HIDE_DEV)
    page.wait_for_timeout(ms)


def main() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        context.grant_permissions(["microphone"], origin=BASE)
        page = context.new_page()

        # Landing: hero and the four modules.
        page.goto(BASE + "/", wait_until="networkidle"); settle(page)
        page.mouse.move(1500, 300); page.wait_for_timeout(500)
        page.screenshot(path=str(SHOTS / "landing-hero.png"))
        page.evaluate("document.querySelector('#modulos').scrollIntoView()"); page.wait_for_timeout(1600)
        page.evaluate("window.scrollBy(0, -40)"); page.wait_for_timeout(600)
        page.screenshot(path=str(SHOTS / "landing-modules.png"))

        # Hunter with a finished search.
        json_route(page, "**/api/hunter/searches", {"items": [HUNTER_JOB]})
        page.goto(PREVIEW + "?workspace=hunter", wait_until="networkidle"); settle(page)
        page.get_by_label("Quem você procura").fill("Dentistas sem site"); page.get_by_label("Cidade ou região").fill("Porto Alegre")
        page.wait_for_timeout(300); page.screenshot(path=str(SHOTS / "hunter.png"))

        # Contacts and daily queue.
        page.goto(PREVIEW + "?workspace=contacts", wait_until="networkidle"); settle(page)
        page.screenshot(path=str(SHOTS / "contacts.png"))
        page.goto(PREVIEW + "?workspace=contacts&view=queue", wait_until="networkidle"); settle(page)
        page.screenshot(path=str(SHOTS / "queue.png"))

        # WhatsApp inbox and automation rules.
        page.goto(PREVIEW + "?workspace=whatsapp", wait_until="load"); settle(page, 2000)
        page.screenshot(path=str(SHOTS / "whatsapp-inbox.png"))
        json_route(page, "**/api/whatsapp-web/config", WA_CONFIG)
        json_route(page, "**/api/whatsapp-web/events", WA_EVENTS)
        page.goto(PREVIEW + "?workspace=automation", wait_until="load"); settle(page, 2000)
        # Frame the rules themselves (scroll past the page header).
        page.evaluate("document.querySelector('main .overflow-y-auto').scrollTop = 175"); page.wait_for_timeout(400)
        page.screenshot(path=str(SHOTS / "whatsapp-automation.png"))

        # Chat thread.
        json_route(page, "**/api/chat/status", STATUS)
        json_route(page, "**/api/chat/messages", CHAT_REPLY)
        page.goto(PREVIEW + "?workspace=chat", wait_until="networkidle"); settle(page)
        page.evaluate("localStorage.clear()"); page.reload(wait_until="networkidle"); settle(page)
        page.get_by_label("Sua mensagem para a Kiara").fill("Kiara, o que eu priorizo hoje?")
        page.get_by_role("button", name="Enviar").click()
        expect(page.get_by_text("Quer que eu escreva a mensagem da proposta?")).to_be_visible(timeout=10000)
        page.wait_for_timeout(600); page.screenshot(path=str(SHOTS / "chat.png"))
        browser_voice = context.new_page()
        browser_voice.add_init_script(FAKE_VOICE)
        json_route(browser_voice, "**/api/chat/status", STATUS)
        json_route(browser_voice, "**/api/chat/messages", {"text": "Hoje, comece pela proposta da Clínica Sorriso Vivo e depois faça a primeira abordagem à Odonto Centro POA."})
        browser_voice.goto(PREVIEW + "?workspace=chat", wait_until="networkidle"); settle(browser_voice)
        browser_voice.get_by_role("button", name="Conversar por voz").click()
        expect(browser_voice.get_by_text("Falando…")).to_be_visible(timeout=10000)
        browser_voice.wait_for_timeout(900); browser_voice.screenshot(path=str(SHOTS / "voice.png"))
        browser_voice.close()

        # Automation: run the CRM digest template, then the ads cost panel.
        json_route(page, "**/api/pipeline", LEADS)
        json_route(page, "**/api/chat/messages", AUTOMATION_REPLY)
        page.goto(PREVIEW + "?workspace=automation-flow", wait_until="networkidle"); settle(page)
        page.evaluate("localStorage.clear()"); page.reload(wait_until="networkidle"); settle(page)
        page.get_by_role("button", name="Resumo diário do CRM").first.click(); page.wait_for_timeout(700)
        page.get_by_role("button", name="Executar", exact=True).click()
        expect(page.get_by_text("Execução concluída")).to_be_visible(timeout=15000)
        page.wait_for_timeout(700); page.screenshot(path=str(SHOTS / "automation-run.png"))
        page.get_by_role("button", name="Campanha Meta + Google").first.click(); page.wait_for_timeout(700)
        page.locator("[data-node-id]").filter(has_text="Anúncio Meta").click(); page.wait_for_timeout(500)
        page.get_by_label("Público").fill("Donos de clínicas, 30 a 55 anos, Porto Alegre e região")
        page.wait_for_timeout(400); page.screenshot(path=str(SHOTS / "automation-ads.png"))
        browser.close()
    print("shots:", sorted(path.name for path in SHOTS.glob("*.png")))


if __name__ == "__main__":
    main()
