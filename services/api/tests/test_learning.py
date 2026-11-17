from kiara_api import learning


def row(query, location, searches=1, results=10, wa=5, nosite=3, added=0, advanced=0, won=0):
    return {"query": query, "location": location, "searches": searches, "results": results, "with_whatsapp": wa,
            "without_website": nosite, "added": added, "advanced": advanced, "won": won}


def test_niche_and_city_are_normalized():
    assert learning.niche_of("Dentistas sem site em Porto Alegre") == "dentistas sem site"
    assert learning.niche_of("Clínicas de Estética") == "clinicas de estetica"
    assert learning.city_of("Porto Alegre - RS") == "porto alegre"
    assert learning.city_of("") == ""


def test_lessons_put_what_works_first_then_what_wastes_searches():
    facts = learning.lessons([
        row("Dentistas", "Porto Alegre", added=6, advanced=3, won=1),
        row("Academias", "Canoas", searches=3, results=40, added=0),
        row("Pet shops", "Porto Alegre", added=2, advanced=0),
    ])
    assert facts[0].startswith('Buscas por "Dentistas" em Porto Alegre trouxeram 6 leads') and "1 vendas" in facts[0]
    assert any("Academias" in fact and "nenhum virou lead" in fact for fact in facts)
    assert any("WhatsApp público" in fact for fact in facts) and len(facts) <= learning.LESSONS
    assert learning.lessons([]) == []


def test_general_patterns_only_count_and_need_two_workspaces():
    first = [row("Dentistas sem site em Porto Alegre", "Porto Alegre - RS", results=20, wa=10, added=4, advanced=2)]
    second = [row("dentistas sem site", "porto alegre", results=10, wa=2, added=2, advanced=1)]
    alone = [row("Academias", "Canoas", results=30, added=5, advanced=4)]
    patterns = learning.aggregate([first, second, alone])
    dentists = next(item for item in patterns if item["niche"] == "dentistas sem site")
    assert dentists == {"niche": "dentistas sem site", "city": "porto alegre", "searches": 2, "results": 30, "with_whatsapp": 12,
                        "without_website": 6, "added": 6, "advanced": 3, "won": 0, "workspaces": 2}
    assert set(dentists) == {"niche", "city", "searches", "results", "with_whatsapp", "without_website", "added", "advanced", "won", "workspaces"}
    lines = learning.pattern_lines(patterns)
    assert len(lines) == 1 and "dentistas sem site" in lines[0] and "40% com WhatsApp" in lines[0]
    assert "academias" not in learning.prompt_block(patterns).lower()      # one workspace alone is never shown


def test_vault_has_obsidian_links_and_no_workspace_data():
    patterns = learning.aggregate([[row("Dentistas", "Porto Alegre", results=20, added=4, advanced=2)],
                                   [row("Dentistas", "Porto Alegre", results=20, added=1, advanced=1)]])
    notes = learning.vault_notes(patterns, workspaces=2)
    assert set(notes) == {"Kiara/Padrões gerais.md", "Kiara/Como a Kiara aprende.md", "Kiara/Nichos/Dentistas.md",
                          "Kiara/O que a Kiara leu.md"}
    assert "[[Dentistas]]" in notes["Kiara/Padrões gerais.md"] and "[[Padrões gerais]]" in notes["Kiara/Nichos/Dentistas.md"]
    assert "| Porto Alegre | 2 | 40 | 5 | 3 | 0 |" in notes["Kiara/Nichos/Dentistas.md"]


def test_team_notes_become_guidance_without_secrets_or_drafts():
    files = {
        "Ensinar a Kiara/Tom de voz.md": "---\ntags: [kiara]\n---\nSeja direta. Veja [[Preços|a tabela]].\nsenha: abc123\nNunca peça a senha do cliente.\n%%só para mim%%\n",
        "Ensinar a Kiara/_rascunho.md": "ainda não",
        "Ensinar a Kiara/../fora.md": "fora",
        "Kiara/Padrões gerais.md": "gerado pelo servidor",
        "Ensinar a Kiara/Cartão.md": "4111 1111 1111 1111",
    }
    items = learning.guide_items(files)
    assert [item["title"] for item in items] == ["Tom de voz"]
    body = items[0]["body"]
    assert "a tabela" in body and "[[" not in body and "abc123" not in body and "só para mim" not in body
    assert "Nunca peça a senha do cliente." in body          # talking about passwords is fine, a value is not
    block = learning.guides_block(items)
    assert "Orientações do time da Kiara" in block and "Tom de voz" in block
    assert learning.guides_block([]) == ""


def test_guides_respect_the_prompt_budget_and_show_in_the_vault():
    items = [{"path": f"Ensinar a Kiara/N{i}.md", "title": f"N{i}", "body": "x" * learning.GUIDE_CHARS} for i in range(10)]
    assert len(learning.guides_block(items)) < learning.GUIDES_TOTAL + 400
    notes = learning.vault_notes([], workspaces=1, guides=items[:2])
    assert "- Sempre: N0 (" in notes["Kiara/O que a Kiara leu.md"] and "Ensinar a Kiara" in notes["Kiara/Como a Kiara aprende.md"]


def test_skills_from_subfolders_reach_only_the_conversations_about_them():
    guides = [
        {"path": "Ensinar a Kiara/Tom de voz.md", "title": "Tom de voz", "body": "Seja direta e gentil."},
        {"path": "Ensinar a Kiara/Helpdesk/Wi-Fi instável.md", "title": "Wi-Fi instável", "body": "1. Medir sinal perto do roteador"},
        {"path": "Ensinar a Kiara/Helpdesk/Impressora não imprime.md", "title": "Impressora não imprime", "body": "1. Ver fila de impressão"},
    ]
    about_wifi = learning.guides_block(guides, "meu wifi está instável e cai toda hora")
    assert "Seja direta" in about_wifi and "Medir sinal" in about_wifi and "fila de impressão" not in about_wifi
    unrelated = learning.guides_block(guides, "quanto custa o plano?")
    assert "Seja direta" in unrelated and "Medir sinal" not in unrelated
    assert "Helpdesk: Impressora não imprime, Wi-Fi instável" in unrelated      # titles are always known
