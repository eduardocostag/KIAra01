import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.scraping_adapters import parse_with_scrapling


def test_visible_contacts_exclude_nested_scripts_and_hidden_content():
    html = """<html><body>Clinica Aurora
      <div><p>Contato: contato@aurora.example</p>
        <script>tracking@vendor.example +5511999999999</script>
        <style>.banner {content: 'fake@vendor.example'}</style>
        <noscript>outdated@vendor.example</noscript>
        <template>template@vendor.example<a href="https://wa.me/5511999999999">Hidden contact</a></template>
        <div hidden><span>hidden@vendor.example</span></div>
        <div aria-hidden="true"><span>invisible@vendor.example</span><a href="mailto:hidden@vendor.example">Hidden mail</a></div>
        <a hidden href="https://wa.me/5511888888888">Hidden link</a>
      </div><a href="/contato">Fale conosco</a>
    </body></html>"""
    text, links = parse_with_scrapling(html, "https://aurora.example")
    assert text == "Clinica Aurora Contato: contato@aurora.example Fale conosco"
    assert links == ["https://aurora.example/contato"]


def test_parser_preserves_direct_body_text_and_text_limit():
    text, _ = parse_with_scrapling("<body>Contato direto <p>" + "x" * 45000 + "</p></body>", "https://example.com")
    assert text.startswith("Contato direto ")
    assert len(text) == 40000
