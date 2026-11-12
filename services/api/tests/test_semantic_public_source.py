import sys
from pathlib import Path
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api import scraping_adapters


def test_semantic_graph_uses_observed_bounded_content_instead_of_browser(monkeypatch):
    captured = {}

    class Graph:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return {"activity": "dental"}

    graphs = ModuleType("scrapegraphai.graphs")
    graphs.SmartScraperGraph = Graph
    monkeypatch.setitem(sys.modules, "scrapegraphai.graphs", graphs)
    monkeypatch.setenv("KIARA_SCRAPEGRAPH_MODEL", "ollama/local")
    monkeypatch.setattr(scraping_adapters, "fetch_public_with_scrapling",
                        lambda url: ("Dental <script>ignored</script> " + "x" * 15000, [], url))
    assert scraping_adapters.analyze_with_scrapegraph("https://example.com", "Activity") == {"activity": "dental"}
    assert captured["source"].startswith("<html><body>Dental &lt;script&gt;")
    assert "<script>" not in captured["source"]
    assert len(captured["source"]) < 12100


def test_semantic_graph_rejects_empty_observed_page(monkeypatch):
    graphs = ModuleType("scrapegraphai.graphs")
    graphs.SmartScraperGraph = lambda **kwargs: pytest.fail("Empty pages must not call a model")
    monkeypatch.setitem(sys.modules, "scrapegraphai.graphs", graphs)
    monkeypatch.setenv("KIARA_SCRAPEGRAPH_MODEL", "ollama/local")
    monkeypatch.setattr(scraping_adapters, "fetch_public_with_scrapling", lambda url: (" ", [], url))
    with pytest.raises(ValueError, match="empty_public_page"):
        scraping_adapters.analyze_with_scrapegraph("https://example.com", "Activity")
