"""Offline, replaceable embedding boundary. No credentials or outbound calls."""

import asyncio
import hashlib
import math
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

BATCH_SIZE = 16
TOTAL_TIMEOUT = 30
BATCH_TIMEOUT = 5


class EmbeddingSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)
    model: str = Field(min_length=1, max_length=100)
    dimensions: int = Field(ge=1, le=2000)


class EmbeddingError(Exception):
    pass


class EmbeddingProvider(Protocol):
    spec: EmbeddingSpec

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class FakeEmbeddingProvider:
    """Deterministic lifecycle fixture, not a semantic embedding model."""

    spec = EmbeddingSpec(model="fake-sha256-v1", dimensions=32)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[(b - 127.5) / 127.5 for b in hashlib.sha256(t.encode()).digest()] for t in texts]


def provider() -> EmbeddingProvider:
    return FakeEmbeddingProvider()


async def embed_chunks(provider: EmbeddingProvider, texts: list[str]) -> list[list[float]]:
    if not texts or len(texts) > 132 or any(not t or len(t) > 2000 for t in texts):
        raise EmbeddingError("invalid_input")
    spec = EmbeddingSpec.model_validate(provider.spec)
    vectors = []
    try:
        async with asyncio.timeout(TOTAL_TIMEOUT):
            for start in range(0, len(texts), BATCH_SIZE):
                batch = texts[start : start + BATCH_SIZE]
                async with asyncio.timeout(BATCH_TIMEOUT):
                    result = await provider.embed(batch)
                if not isinstance(result, list) or len(result) != len(batch):
                    raise EmbeddingError("invalid_output")
                for vector in result:
                    if (
                        not isinstance(vector, list)
                        or len(vector) != spec.dimensions
                        or any(
                            type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e30
                            for v in vector
                        )
                        or not any(vector)
                    ):
                        raise EmbeddingError("invalid_output")
                vectors.extend(result)
    except TimeoutError:
        raise EmbeddingError("timeout") from None
    return vectors
