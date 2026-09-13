from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.ai.adapters.openai import OpenAIProvider
from app.ai.contracts import (
    AIProviderAuthenticationFailed,
    AIProviderError,
    AIProviderInvalidResponse,
    AIProviderRateLimited,
    AIProviderTimeout,
    AIProviderUnavailable,
    AIRequest,
    AIStructuredResponse,
)

REQUEST = AIRequest("question_tutor", "system", "user", 800)
STRUCTURED_REQUEST = AIRequest(
    "question_generation",
    "system",
    "user",
    4_000,
    structured_response=AIStructuredResponse(
        "question_generation",
        {"type": "object", "properties": {}, "additionalProperties": False},
    ),
    max_output_chars=32_000,
)


@pytest.mark.asyncio
async def test_openai_adapter_maps_responses_request_and_result() -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(
                return_value=SimpleNamespace(
                    output_text="Tutor response",
                    model="configured-model",
                    usage=SimpleNamespace(input_tokens=10, output_tokens=5),
                    _request_id="openai-request",
                )
            )
        )
    )
    provider = OpenAIProvider(client, "configured-model", 20)
    result = await provider.generate(REQUEST)
    client.responses.create.assert_awaited_once_with(
        model="configured-model",
        instructions="system",
        input="user",
        max_output_tokens=800,
        store=False,
        timeout=20,
    )
    assert result.content == "Tutor response"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.provider_request_id == "openai-request"


@pytest.mark.asyncio
async def test_openai_adapter_maps_structured_response_request() -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(
                return_value=SimpleNamespace(
                    status="completed",
                    output_text='{"candidates": []}',
                    model="configured-model",
                    usage=SimpleNamespace(input_tokens=10, output_tokens=5),
                    _request_id="structured-request",
                )
            )
        )
    )
    result = await OpenAIProvider(client, "configured-model", 20).generate(
        STRUCTURED_REQUEST
    )
    client.responses.create.assert_awaited_once_with(
        model="configured-model",
        instructions="system",
        input="user",
        max_output_tokens=4_000,
        store=False,
        timeout=20,
        text={
            "format": {
                "type": "json_schema",
                "name": "question_generation",
                "schema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                "strict": True,
            }
        },
    )
    assert result.content == '{"candidates": []}'
    assert result.provider_request_id == "structured-request"


@pytest.mark.asyncio
async def test_openai_adapter_rejects_incomplete_structured_response() -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(
                return_value=SimpleNamespace(status="incomplete", output_text="partial")
            )
        )
    )
    with pytest.raises(AIProviderInvalidResponse):
        await OpenAIProvider(client, "model", 20).generate(STRUCTURED_REQUEST)


def test_openai_adapter_disables_sdk_retries() -> None:
    client = Mock()
    with patch("app.ai.adapters.openai.openai.AsyncOpenAI", return_value=client) as factory:
        provider = OpenAIProvider.create(
            api_key="not-a-real-key", model="replaceable-model", timeout_seconds=20
        )
    factory.assert_called_once_with(
        api_key="not-a-real-key", max_retries=0, timeout=20
    )
    assert provider.model_name == "replaceable-model"


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["", "   "])
async def test_openai_adapter_rejects_empty_content(content: str) -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=AsyncMock(return_value=SimpleNamespace(output_text=content))
        )
    )
    with pytest.raises(AIProviderInvalidResponse):
        await OpenAIProvider(client, "model", 20).generate(REQUEST)


@pytest.mark.asyncio
async def test_openai_adapter_sanitizes_unexpected_exception() -> None:
    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("secret body")))
    )
    with pytest.raises(AIProviderError) as caught:
        await OpenAIProvider(client, "model", 20).generate(REQUEST)
    assert "secret body" not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sdk_exception_name", "expected_exception"),
    [
        ("APITimeoutError", AIProviderTimeout),
        ("RateLimitError", AIProviderRateLimited),
        ("AuthenticationError", AIProviderAuthenticationFailed),
        ("PermissionDeniedError", AIProviderAuthenticationFailed),
        ("APIConnectionError", AIProviderUnavailable),
    ],
)
async def test_openai_adapter_maps_known_sdk_errors(
    sdk_exception_name: str, expected_exception: type[Exception]
) -> None:
    sdk_exception = type(f"Fake{sdk_exception_name}", (Exception,), {})
    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(side_effect=sdk_exception("private")))
    )
    with patch.object(
        __import__("app.ai.adapters.openai", fromlist=["openai"]).openai,
        sdk_exception_name,
        sdk_exception,
    ):
        with pytest.raises(expected_exception) as caught:
            await OpenAIProvider(client, "model", 20).generate(REQUEST)
    assert "private" not in str(caught.value)


@pytest.mark.asyncio
async def test_openai_adapter_maps_provider_5xx_to_unavailable() -> None:
    class FakeStatusError(Exception):
        status_code = 500

    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(side_effect=FakeStatusError("private")))
    )
    with patch.object(
        __import__("app.ai.adapters.openai", fromlist=["openai"]).openai,
        "APIStatusError",
        FakeStatusError,
    ):
        with pytest.raises(AIProviderUnavailable):
            await OpenAIProvider(client, "model", 20).generate(REQUEST)
