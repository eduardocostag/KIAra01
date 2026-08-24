from app.memory.embeddings import LocalHashEmbeddingProvider, cosine_similarity


def test_local_embeddings_are_deterministic_and_semantically_overlap():
    provider = LocalHashEmbeddingProvider(64)
    a, b, c = provider.embed(["servidor windows lento", "windows servidor", "receita de bolo"])
    assert a == provider.embed(["servidor windows lento"])[0]
    assert cosine_similarity(a, b) > cosine_similarity(a, c)
