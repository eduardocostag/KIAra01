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
    assert set(notes) == {"Kiara/Padrões gerais.md", "Kiara/Como a Kiara aprende.md", "Kiara/Nichos/Dentistas.md"}
    assert "[[Dentistas]]" in notes["Kiara/Padrões gerais.md"] and "[[Padrões gerais]]" in notes["Kiara/Nichos/Dentistas.md"]
    assert "| Porto Alegre | 2 | 40 | 5 | 3 | 0 |" in notes["Kiara/Nichos/Dentistas.md"]
