"""Visual smoke preview for the dashboard CSS, without authenticated lead data."""
from __future__ import annotations

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

WEB_ROOT = Path(__file__).parents[1]
STYLES = [WEB_ROOT / ".next" / "static" / "chunks" / "44m3qusy0k8cd.css",
          WEB_ROOT / "src" / "app" / "(app)" / "app" / "orbit-dashboard.css"]
OUT = Path(__file__).parent / "visual-artifacts"

HTML = """<div class="kiara-workspace min-h-screen bg-background text-foreground">
  <aside class="kiara-sidebar"><div class="kiara-shell-brand">🟣 &nbsp; KIARA</div><div class="kiara-shell-nav"><div class="kiara-shell-nav-link is-active">Visão geral</div><div class="kiara-shell-nav-link">Leads</div><div class="kiara-shell-nav-link">Inbox</div></div></aside>
  <div class="preview-content"><header class="app-shell-header"><span class="kiara-shell-search">⌕ &nbsp; Pesquisar leads...</span><span>♧ &nbsp; ⚙</span></header>
  <main><div class="kiara-dashboard kiara-orbit-dashboard">
    <section class="kiara-dashboard-hero"><div class="kiara-dashboard-copy"><p class="kiara-dashboard-eyebrow">QUINTA-FEIRA, 15 DE SETEMBRO</p><h1><span>Converse.</span><span>Entenda.</span><span class="kiara-dashboard-gradient-word">Conquiste.</span></h1><p class="kiara-dashboard-lead">Você tem 18 leads novos esperando uma primeira abordagem.</p><a class="kiara-dashboard-cta">Começar minha fila →</a><div class="kiara-dashboard-capabilities"><a>⌕ Encontrar leads</a><a>◉ Inbox</a><a>⚙ Integrações</a></div></div>
    <div class="kiara-dashboard-planet"><div class="kiara-orbit-scene"><span class="kiara-orbit-glow"></span><span class="kiara-orbit-ring kiara-orbit-ring-one"></span><span class="kiara-orbit-ring kiara-orbit-ring-two"></span><span class="kiara-orbit-ring kiara-orbit-ring-three"></span><span class="kiara-orbit-arc kiara-orbit-arc-one"></span><span class="kiara-orbit-arc kiara-orbit-arc-two"></span><span class="kiara-orb kiara-orb-lg"><span class="kiara-orb-face"><i></i><i></i></span></span><span class="kiara-orbit-spark kiara-orbit-spark-one"></span><span class="kiara-orbit-spark kiara-orbit-spark-two"></span><span class="kiara-orbit-callout kiara-orbit-callout-top">✦ Buscas organizadas</span><span class="kiara-orbit-callout kiara-orbit-callout-right">✦ Próxima ação clara</span><span class="kiara-orbit-callout kiara-orbit-callout-bottom">✦ Fontes públicas</span></div></div>
    <div class="kiara-dashboard-metrics"><div class="kiara-dashboard-metric"><span class="kiara-dashboard-metric-icon">▥</span><div><p class="kiara-dashboard-metric-value">18</p><p class="kiara-dashboard-metric-label">Novos leads</p></div></div><div class="kiara-dashboard-metric"><span class="kiara-dashboard-metric-icon">◷</span><div><p class="kiara-dashboard-metric-value">0</p><p class="kiara-dashboard-metric-label">Follow-ups</p></div></div><div class="kiara-dashboard-metric"><span class="kiara-dashboard-metric-icon">▢</span><div><p class="kiara-dashboard-metric-value">0</p><p class="kiara-dashboard-metric-label">Conversas abertas</p></div></div></div></section>
    <section class="kiara-dashboard-table"><div class="kiara-dashboard-table-head"><h2>Leads recentes</h2><span>Ver todos →</span></div><table><thead><tr><th>Lead</th><th>Origem</th><th>Tempo</th><th>Status</th></tr></thead><tbody><tr><td>Consulta Fácil</td><td>Google Maps</td><td>Há 2 min</td><td>Novo</td></tr><tr><td>Clínica Odontológica</td><td>Instagram</td><td>Há 8 min</td><td>Novo</td></tr><tr><td>Consultório Prime</td><td>Web pública</td><td>Há 15 min</td><td>Novo</td></tr></tbody></table></section>
  </div></main></div></div>"""


def preview(page, width: int, height: int, name: str) -> dict[str, object]:
    page.set_viewport_size({"width": width, "height": height})
    page.goto("about:blank")
    page.evaluate("document.documentElement.classList.add('dark')")
    for stylesheet in STYLES:
        page.add_style_tag(path=str(stylesheet))
    page.add_style_tag(content=".kiara-workspace{display:block!important}.preview-content{position:absolute;top:0;left:0;right:0;padding-left:202px;padding-top:64px}.preview-content main{padding:28px}.preview-content header{position:fixed;top:0;left:202px;right:0;height:64px;display:flex;align-items:center;justify-content:flex-end;padding:0 28px;z-index:20}.kiara-sidebar{width:202px;display:flex;flex-direction:column;padding:24px 12px}.kiara-shell-brand{margin-bottom:28px}.kiara-shell-nav-link{padding:12px}@media(max-width:767px){.preview-content{padding-left:0}.kiara-sidebar{display:none}.preview-content header{left:0}.preview-content main{padding:16px}}")
    page.evaluate("(html) => { document.body.innerHTML = html; document.body.className = ''; }", HTML)
    page.wait_for_timeout(400)
    first_transform = page.locator(".kiara-orbit-ring-one").evaluate("el => getComputedStyle(el).transform")
    page.wait_for_timeout(300)
    second_transform = page.locator(".kiara-orbit-ring-one").evaluate("el => getComputedStyle(el).transform")
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    report = page.evaluate("""() => ({
      viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth,
      content: document.querySelector('.preview-content').getBoundingClientRect().toJSON(),
      main: document.querySelector('.preview-content main').getBoundingClientRect().toJSON(),
      hero: document.querySelector('.kiara-dashboard-hero').getBoundingClientRect().toJSON(),
      orb: document.querySelector('.kiara-orbit-scene .kiara-orb').getBoundingClientRect().toJSON(),
      metrics: document.querySelector('.kiara-dashboard-metrics').getBoundingClientRect().toJSON(),
      ringAnimation: getComputedStyle(document.querySelector('.kiara-orbit-ring-one')).animationName
    })""")
    report["ring_transform_changed"] = first_transform != second_transform
    return report


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        reports = [preview(page, 912, 605, "orbit-912"), preview(page, 390, 844, "orbit-390")]
        reduced = browser.new_page(reduced_motion="reduce")
        reports.append(preview(reduced, 912, 605, "orbit-reduced"))
        print(json.dumps(reports, ensure_ascii=False))
        reduced.close()
        browser.close()


if __name__ == "__main__":
    main()
