from types import SimpleNamespace

import pytest

from app.providers.embeddings import (
    EmbeddingProviderError,
    FoundryLocalEmbeddingProvider,
)


class StubEmbeddingClient:
    def generate_embeddings(self, texts: list[str]) -> SimpleNamespace:
        assert texts == ["first", "second"]
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[0.0, 1.0]),
                SimpleNamespace(index=0, embedding=[1.0, 0.0]),
            ]
        )

    def generate_embedding(self, text: str) -> SimpleNamespace:
        assert text == "question"
        return SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[0.5, 0.5])]
        )


def test_foundry_provider_preserves_batch_order_and_embeds_query() -> None:
    provider = FoundryLocalEmbeddingProvider("test-model")
    provider._client = StubEmbeddingClient()

    assert provider.embed_documents(["first", "second"]) == [
        [1.0, 0.0],
        [0.0, 1.0],
    ]
    assert provider.embed_query("question") == [0.5, 0.5]


def test_foundry_provider_rejects_invalid_vector_counts() -> None:
    provider = FoundryLocalEmbeddingProvider("test-model")
    provider._client = SimpleNamespace(
        generate_embeddings=lambda texts: SimpleNamespace(data=[])
    )

    with pytest.raises(EmbeddingProviderError):
        provider.embed_documents(["missing"])
