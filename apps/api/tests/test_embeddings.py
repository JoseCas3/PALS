from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.embeddings.contracts import (
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingUnavailableError,
)
from app.embeddings.fake import FakeEmbeddingProvider
from app.embeddings.openai import OpenAIEmbeddingProvider
from app.embeddings.service import EmbeddingService


@pytest.mark.asyncio
async def test_fake_embeddings_are_stable_distinct_finite_and_1536_dimensions() -> None:
    provider = FakeEmbeddingProvider()

    first = tuple(await provider.embed(["alpha", "beta", "alpha"]))
    second = tuple(await FakeEmbeddingProvider().embed(["alpha", "beta", "alpha"]))

    assert first == second
    assert first[0].vector == first[2].vector
    assert first[0].vector != first[1].vector
    assert len(first[0].vector) == 1536


@pytest.mark.asyncio
async def test_service_splits_batches_and_preserves_global_order() -> None:
    provider = FakeEmbeddingProvider()
    service = EmbeddingService(provider, batch_size=2, dimensions=1536)

    vectors = await service.embed(["zero", "one", "two", "three", "four"])

    expected = tuple(item.vector for item in await FakeEmbeddingProvider().embed(
        ["zero", "one", "two", "three", "four"]
    ))
    assert vectors == expected
    assert provider.call_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("cardinality", EmbeddingError),
        ("ordering", EmbeddingError),
        ("nonfinite", EmbeddingError),
        ("infinity", EmbeddingError),
        ("wrong_dimensions", EmbeddingDimensionMismatchError),
        ("unavailable", EmbeddingUnavailableError),
        ("timeout", EmbeddingUnavailableError),
    ],
)
async def test_service_rejects_invalid_or_unavailable_provider_results(
    failure: str, expected: type[EmbeddingError]
) -> None:
    provider = FakeEmbeddingProvider(failure=failure)  # type: ignore[arg-type]

    with pytest.raises(expected):
        await EmbeddingService(provider, batch_size=2, dimensions=1536).embed(["a", "b"])


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_call", [1, 2, 3])
async def test_failure_in_any_batch_returns_no_partial_result(failure_call: int) -> None:
    provider = FakeEmbeddingProvider(failure="unavailable", failure_call=failure_call)
    service = EmbeddingService(provider, batch_size=1, dimensions=1536)

    with pytest.raises(EmbeddingUnavailableError):
        await service.embed(["first", "middle", "final"])


@pytest.mark.asyncio
async def test_openai_adapter_explicitly_requests_model_dimensions_and_preserves_indexes() -> None:
    calls: list[dict[str, object]] = []

    class Embeddings:
        async def create(self, **kwargs: object) -> object:
            calls.append(kwargs)
            return SimpleNamespace(
                data=[
                    SimpleNamespace(index=0, embedding=[0.0] * 1536),
                    SimpleNamespace(index=1, embedding=[1.0] * 1536),
                ]
            )

    client = SimpleNamespace(embeddings=Embeddings())
    provider = OpenAIEmbeddingProvider(
        api_key="unused",
        model_name="text-embedding-3-small",
        dimensions=1536,
        timeout_seconds=20,
        client=client,
    )

    response = await provider.embed(["first", "second"])

    assert calls == [
        {
            "input": ["first", "second"],
            "model": "text-embedding-3-small",
            "dimensions": 1536,
        }
    ]
    assert [item.index for item in response] == [0, 1]


@pytest.mark.asyncio
async def test_openai_provider_without_key_fails_only_when_embedding_is_requested() -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="",
        model_name="text-embedding-3-small",
        dimensions=1536,
        timeout_seconds=20,
    )

    with pytest.raises(EmbeddingUnavailableError):
        await provider.embed(["safe"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(),
        SimpleNamespace(data=None),
        SimpleNamespace(data=[SimpleNamespace(index=0)]),
        SimpleNamespace(data=[SimpleNamespace(index=0, embedding=None)]),
    ],
)
async def test_openai_malformed_response_maps_to_safe_embedding_failure(
    response: object,
) -> None:
    class Embeddings:
        async def create(self, **_: object) -> object:
            return response

    provider = OpenAIEmbeddingProvider(
        api_key="unused",
        model_name="text-embedding-3-small",
        dimensions=1536,
        timeout_seconds=20,
        client=SimpleNamespace(embeddings=Embeddings()),
    )

    with pytest.raises(EmbeddingError, match="invalid response") as raised:
        await provider.embed(["private query"])
    assert "private query" not in str(raised.value)


@pytest.mark.asyncio
async def test_openai_unexpected_client_failure_maps_to_embedding_failed() -> None:
    class Embeddings:
        async def create(self, **_: object) -> object:
            raise RuntimeError("private provider payload")

    provider = OpenAIEmbeddingProvider(
        api_key="unused",
        model_name="text-embedding-3-small",
        dimensions=1536,
        timeout_seconds=20,
        client=SimpleNamespace(embeddings=Embeddings()),
    )

    with pytest.raises(EmbeddingError) as raised:
        await provider.embed(["private document text"])
    assert str(raised.value) == "Embedding provider failed"
    assert "private" not in str(raised.value)
