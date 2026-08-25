from __future__ import annotations

from app.core.context import ContextManager
from app.knowledge import KnowledgeStore
from app.models import ScreenContext


class TinyEmbeddings:
    def embed(self, texts):
        return [[1.0, 0.0] if "felino" in text.casefold() else [0.0, 1.0] for text in texts]


def test_ingests_txt_chunks_metadata_and_deduplicates(tmp_path) -> None:
    source = tmp_path / "manual.txt"
    source.write_text("Kiara organiza tarefas. " * 30, encoding="utf-8")
    store = KnowledgeStore(tmp_path / "knowledge.db", chunk_size=100, chunk_overlap=10)
    first = store.ingest(source, {"category": "manual"})
    duplicate = store.ingest(source)
    results = store.search("organiza tarefas", limit=20)

    assert first.chunks_added > 1
    assert duplicate.deduplicated is True
    assert duplicate.document_id == first.document_id
    assert results[0].metadata["category"] == "manual"
    assert results[0].source == str(source.resolve())


def test_markdown_and_pdf_extractor_contract(tmp_path) -> None:
    markdown = tmp_path / "notes.md"
    markdown.write_text("# Projeto\nCronograma trimestral", encoding="utf-8")
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"fake-pdf")
    store = KnowledgeStore(
        tmp_path / "knowledge.db", extractors={".pdf": lambda _path: "Relatório financeiro"}
    )

    assert store.ingest(markdown).chunks_added == 1
    assert store.ingest(pdf).chunks_added == 1
    assert store.search("financeiro")[0].metadata["extension"] == ".pdf"


def test_hybrid_search_uses_embeddings_and_lexical_fallback(tmp_path) -> None:
    cat = tmp_path / "cat.txt"
    cat.write_text("felino doméstico", encoding="utf-8")
    dog = tmp_path / "dog.txt"
    dog.write_text("animal doméstico", encoding="utf-8")
    store = KnowledgeStore(tmp_path / "knowledge.db", embedding_provider=TinyEmbeddings())
    store.ingest(cat)
    store.ingest(dog)
    assert store.search("felino")[0].source == str(cat.resolve())

    store._fts = False
    assert store.search("animal")[0].source == str(dog.resolve())


def test_context_manager_surfaces_relevant_knowledge(tmp_path) -> None:
    source = tmp_path / "policy.txt"
    source.write_text("Política de férias: trinta dias", encoding="utf-8")
    store = KnowledgeStore(tmp_path / "knowledge.db")
    store.ingest(source)
    context = ContextManager(lambda: ScreenContext(), knowledge=store)

    assembled = context.assemble("Qual é a política de férias?")
    assert assembled["relevant_knowledge"][0]["content"] == "Política de férias: trinta dias"
    assert assembled["relevant_knowledge"][0]["citation"] == {
        "source": str(source.resolve()),
        "chunk": 0,
    }


def test_relevance_threshold_filters_weak_semantic_matches(tmp_path) -> None:
    source = tmp_path / "animals.txt"
    source.write_text("animal doméstico", encoding="utf-8")
    store = KnowledgeStore(
        tmp_path / "knowledge.db",
        embedding_provider=TinyEmbeddings(),
        relevance_threshold=0.4,
    )
    store.ingest(source)

    assert store.search("assunto sem termos comuns") == []
    assert store.search("assunto sem termos comuns", relevance_threshold=0.3)


def test_results_are_deduplicated_and_diversified_across_sources(tmp_path) -> None:
    duplicate_a = tmp_path / "duplicate-a.txt"
    duplicate_b = tmp_path / "duplicate-b.txt"
    diverse = tmp_path / "diverse.txt"
    duplicate_a.write_text("reinicie o roteador", encoding="utf-8")
    duplicate_b.write_text("reinicie   o roteador", encoding="utf-8")
    diverse.write_text("verifique o roteador e os cabos", encoding="utf-8")
    store = KnowledgeStore(
        tmp_path / "knowledge.db",
        relevance_threshold=0.1,
        max_chunks_per_source=1,
    )
    store.ingest(duplicate_a)
    store.ingest(duplicate_b)
    store.ingest(diverse)

    results = store.search("roteador", limit=10)

    assert len(results) == 2
    assert len({result.content.casefold() for result in results}) == 2
    assert len({result.source for result in results}) == 2


def test_structured_citation_includes_page_when_metadata_provides_it(tmp_path) -> None:
    source = tmp_path / "manual.txt"
    source.write_text("procedimento de diagnóstico", encoding="utf-8")
    store = KnowledgeStore(tmp_path / "knowledge.db")
    store.ingest(source, {"page": 7})

    result = store.search("diagnóstico")[0]

    assert result.citation == {"source": str(source.resolve()), "chunk": 0, "page": 7}


def test_context_budget_bounds_retrieved_knowledge(tmp_path) -> None:
    source = tmp_path / "large.txt"
    source.write_text("procedimento " * 300, encoding="utf-8")
    store = KnowledgeStore(tmp_path / "knowledge.db", chunk_size=700, chunk_overlap=50)
    store.ingest(source)
    context = ContextManager(lambda: ScreenContext(), knowledge=store, knowledge_max_chars=500)

    results = context.assemble("procedimento")["relevant_knowledge"]

    assert sum(len(item["content"]) for item in results) <= 500
