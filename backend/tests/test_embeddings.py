import asyncio

import pytest

from app.embedding_provider import (
    EmbeddingError,
    EmbeddingSpec,
    FakeEmbeddingProvider,
    embed_chunks,
)


def test_fake_embeddings_are_repeatable_and_batches_are_bounded():
    class Recording(FakeEmbeddingProvider):
        sizes = []

        async def embed(self, texts):
            self.sizes.append(len(texts))
            return await super().embed(texts)

    provider = Recording()
    result = asyncio.run(embed_chunks(provider, ["same"] * 33))
    assert provider.sizes == [16, 16, 1]
    assert result[0] == result[-1]
    assert len(result[0]) == 32


@pytest.mark.parametrize(
    "vector",
    [
        [],
        [0.0] * 32,
        [float("nan")] * 32,
        [float("inf")] * 32,
        [True] * 32,
        [1e40] * 32,
        ["1"] * 32,
    ],
)
def test_reject_invalid_vectors(vector):
    class Invalid(FakeEmbeddingProvider):
        async def embed(self, texts):
            return [vector]

    with pytest.raises(EmbeddingError, match="invalid_output"):
        asyncio.run(embed_chunks(Invalid(), ["synthetic"]))


def test_reject_wrong_count():
    class Invalid(FakeEmbeddingProvider):
        async def embed(self, texts):
            return []

    with pytest.raises(EmbeddingError, match="invalid_output"):
        asyncio.run(embed_chunks(Invalid(), ["synthetic"]))


def test_timeout_cancels_provider(monkeypatch):
    monkeypatch.setattr("app.embedding_provider.BATCH_TIMEOUT", 0.01)
    cancelled = []

    class Slow(FakeEmbeddingProvider):
        async def embed(self, texts):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)

    with pytest.raises(EmbeddingError, match="timeout"):
        asyncio.run(embed_chunks(Slow(), ["synthetic"]))
    assert cancelled == [True]


@pytest.mark.parametrize("texts", [[], ["x"] * 133, ["x" * 2001]])
def test_input_bounds(texts):
    with pytest.raises(EmbeddingError, match="invalid_input"):
        asyncio.run(embed_chunks(FakeEmbeddingProvider(), texts))


def test_dimension_bounds():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EmbeddingSpec(model="fake", dimensions=2001)
