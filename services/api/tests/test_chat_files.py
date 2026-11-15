"""Word, spreadsheets, CSV, scanned PDFs, attachments remembered in later turns and pasted links."""
import base64
import io
import zipfile

import pytest
from PIL import Image, ImageDraw

from kiara_api import chat_files, chat_links
from kiara_api.chat_files import DOCX, XLSX, Attachment, AttachmentError
from test_chat_stream import ASK, build, events

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def _zip(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return out.getvalue()


def _b64(raw):
    return base64.b64encode(raw).decode()


def docx():
    return _zip({"word/document.xml": f'<w:document {W}><w:body>'
                 '<w:p><w:r><w:t>Proposta comercial</w:t></w:r></w:p>'
                 '<w:p><w:r><w:t xml:space="preserve">Valor total: </w:t></w:r><w:r><w:t>R$ 18.000</w:t></w:r></w:p>'
                 '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Item</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Preço</w:t></w:r></w:p></w:tc></w:tr>'
                 '<w:tr><w:tc><w:p><w:r><w:t>Site</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>12000</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
                 '</w:body></w:document>'})


def xlsx():
    return _zip({
        "xl/workbook.xml": f'<workbook {S} {R}><sheets><sheet name="Vendas" sheetId="1" r:id="rId1"/>'
                           '<sheet name="Custos" sheetId="2" r:id="rId2"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                      '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
                                      '<Relationship Id="rId2" Target="/xl/worksheets/sheet2.xml"/></Relationships>',
        "xl/sharedStrings.xml": f'<sst {S}><si><t>Mês</t></si><si><t>Total</t></si><si><t>Janeiro</t></si><si><r><t>Fever</t></r><r><t>eiro</t></r></si></sst>',
        "xl/worksheets/sheet1.xml": f'<worksheet {S}><sheetData>'
                                    '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                                    '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>1500.5</v></c></row>'
                                    '<row r="3"><c r="A3" t="s"><v>3</v></c><c r="C3" t="inlineStr"><is><t>sem total</t></is></c></row>'
                                    '</sheetData></worksheet>',
        "xl/worksheets/sheet2.xml": f'<worksheet {S}><sheetData><row r="1"><c r="A1" t="b"><v>1</v></c></row></sheetData></worksheet>',
    })


def scanned_pdf():
    page = Image.new("RGB", (900, 1200), "white")
    ImageDraw.Draw(page).text((80, 100), "NOTA FISCAL 4821 - TOTAL R$ 930,00", fill="black")
    out = io.BytesIO()
    page.save(out, format="PDF", resolution=100)
    return out.getvalue()


def test_word_document_text_keeps_paragraphs_and_tables():
    text = chat_files.docx_text(docx())
    assert text.splitlines() == ["Proposta comercial", "Valor total: R$ 18.000", "Item | Preço", "Site | 12000"]


def test_spreadsheet_every_sheet_with_shared_and_inline_strings():
    text = chat_files.xlsx_text(xlsx())
    assert '[aba "Vendas": 3 linha(s)]' in text and "Mês | Total" in text and "Janeiro | 1500.5" in text
    assert "Fevereiro |  | sem total" in text and '[aba "Custos": 1 linha(s)]\nVERDADEIRO' in text


def test_csv_in_windows_encoding_is_read():
    content, context = chat_files.user_content("some a coluna", [Attachment(name="v.csv", mime="text/csv",
                                                                            data_base64=_b64("cidade;valor\nSão Paulo;10\n".encode("cp1252")))])
    assert "São Paulo;10" in content and "São Paulo;10" in context


def test_office_files_must_really_be_zip_and_bombs_are_refused(monkeypatch):
    with pytest.raises(AttachmentError):
        chat_files.user_content("x", [Attachment(name="a.docx", mime=DOCX, data_base64=_b64(b"MZ not a zip"))])
    with pytest.raises(AttachmentError):
        chat_files.user_content("x", [Attachment(name="a.txt", mime="text/plain", data_base64=_b64(b"\x00\x01binary"))])
    monkeypatch.setattr(chat_files, "MAX_UNZIPPED_BYTES", 100)
    with pytest.raises(AttachmentError, match="grande demais"):
        chat_files.xlsx_text(xlsx(), "grande.xlsx")


def test_scanned_pdf_goes_as_page_pictures():
    content, context = chat_files.user_content("leia", [Attachment(name="nota.pdf", mime="application/pdf", data_base64=_b64(scanned_pdf()))])
    assert isinstance(content, list) and "escaneado" in content[0]["text"]
    assert content[1]["type"] == "image_url" and content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert "PDF escaneado de 1 página" in context


def test_stream_returns_document_text_to_keep_and_history_sends_it_back(monkeypatch):
    api, seen = build(monkeypatch, {"claude/claude-sonnet-5-5": ["Total de R$ 18.000."]})
    got = events(api, {"messages": [{"role": "user", "content": "Quanto custa?"}],
                       "attachments": [{"name": "proposta.docx", "mime": DOCX, "data_base64": _b64(docx())}]})
    kept = got[-1]["file_context"]
    assert "Valor total: R$ 18.000" in kept and kept.startswith("[proposta.docx, documento Word]")
    jpeg = _b64(b"\xff\xd8\xff\xe0" + b"0" * 50)
    events(api, {"messages": [
        {"role": "user", "content": "Quanto custa?", "file_context": kept, "attachments": [{"name": "f.jpg", "mime": "image/jpeg", "data_base64": jpeg}]},
        {"role": "assistant", "content": "Total de R$ 18.000."},
        {"role": "user", "content": "E sem o site?"}]})
    earlier = seen["conversations"][-1][1][1]["content"]
    assert "Arquivos anexados nesta mensagem" in earlier[0]["text"] and "Site | 12000" in earlier[0]["text"]
    assert earlier[1]["image_url"]["url"] == "data:image/jpeg;base64," + jpeg
    assert seen["conversations"][-1][1][-1]["content"] == "E sem o site?"


def test_pasted_link_is_opened_and_kept(monkeypatch):
    monkeypatch.setattr(chat_links, "_read", lambda urls: [{"url": urls[0], "title": "Planos", "text": "Plano Pro: R$ 99 por mês."}])
    api, seen = build(monkeypatch, {"claude/claude-sonnet-5-5": ["O Pro custa R$ 99."]})
    got = events(api, {"messages": [{"role": "user", "content": "Quanto custa o Pro em https://exemplo.com.br/planos?"}]})
    assert {"type": "status", "text": "Abrindo o link…"} in got
    sent = seen["conversations"][0][1][-1]["content"]
    assert "[Conteúdo da página https://exemplo.com.br/planos (Planos)" in sent and "R$ 99 por mês" in sent
    assert got[-1]["file_context"].startswith("[Página https://exemplo.com.br/planos (Planos)]")


def test_unreadable_link_is_said_not_invented(monkeypatch):
    monkeypatch.setattr(chat_links, "_read", lambda urls: [{"url": urls[0], "title": "", "text": ""}])
    api, seen = build(monkeypatch, {"claude/claude-sonnet-5-5": ["Não consegui abrir."]})
    events(api, {"messages": [{"role": "user", "content": "resume https://site.com/x"}]})
    assert "Não foi possível abrir a página https://site.com/x" in seen["conversations"][0][1][-1]["content"]
    got = events(api, {"messages": ASK})
    assert "file_context" not in got[-1]


def test_find_urls_trims_punctuation():
    assert chat_links.find_urls("veja https://a.com/x. e (https://b.com/y), https://w.org/Foo_(bar)!") == [
        "https://a.com/x", "https://b.com/y", "https://w.org/Foo_(bar)"]


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://192.168.1.12:8088/", "http://169.254.169.254/latest/meta-data",
                                 "http://localhost/", "http://[::1]/", "ftp://example.com/", "http://example.com:8080/"])
def test_direct_reading_never_reaches_internal_addresses(url):
    assert chat_links._fetch(url) is None


def test_page_text_drops_scripts_and_keeps_title():
    page = chat_links.page_text("<html><head><title>Loja &amp; Cia</title><script>var x=1</script></head><body><nav>Menu</nav>"
                                "<p>Entregamos em toda a região metropolitana de Porto Alegre.</p><style>p{}</style></body></html>")
    assert page["title"] == "Loja & Cia" and "var x" not in page["text"] and "região metropolitana" in page["text"]


def test_retried_question_brings_back_its_kept_text_and_photo(monkeypatch):
    api, seen = build(monkeypatch, {"claude/claude-sonnet-5-5": ["De novo: R$ 18.000."]})
    jpeg = _b64(b"\xff\xd8\xff\xe0" + b"1" * 50)
    got = events(api, {"messages": [{"role": "user", "content": "Quanto custa?", "file_context": "[proposta.docx, documento Word]\nValor R$ 18.000",
                                     "attachments": [{"name": "f.jpg", "mime": "image/jpeg", "data_base64": jpeg}]}]})
    last = seen["conversations"][-1][1][-1]["content"]
    assert "Valor R$ 18.000" in last[0]["text"] and last[1]["image_url"]["url"].endswith(jpeg)
    assert got[-1]["file_context"].startswith("[proposta.docx")
