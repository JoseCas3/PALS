import asyncio

import pytest

from app.ai.contracts import (
    AIProviderInvalidResponse,
    AIProviderUnavailable,
    AIRequest,
    ProviderResponse,
)
from app.ai.gateway import MAX_AI_OUTPUT_CHARS, AIGateway

REQUEST = AIRequest("question_tutor", "system", "user", 800)


class FakeProvider:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self, response: ProviderResponse | None = None) -> None:
        self.response = response

    async def generate(self, _: AIRequest) -> ProviderResponse:
        if self.response is None:
            raise AIProviderUnavailable(self.provider_name, self.model_name)
        return self.response


@pytest.mark.asyncio
async def test_gateway_normalizes_response_and_metadata() -> None:
    gateway = AIGateway(
        FakeProvider(
            ProviderResponse(
                content="  useful help  ",
                provider="fake",
                model="configured-model",
                input_tokens=12,
                output_tokens=7,
                provider_request_id="request-1",
            )
        ),
        timeout_seconds=1,
    )
    response = await gateway.generate(REQUEST)
    assert response.content == "useful help"
    assert response.provider == "fake"
    assert response.model == "configured-model"
    assert response.input_tokens == 12
    assert response.output_tokens == 7
    assert response.provider_request_id == "request-1"
    assert response.latency_ms >= 0


@pytest.mark.asyncio
async def test_gateway_preserves_nullable_usage() -> None:
    gateway = AIGateway(
        FakeProvider(ProviderResponse("help", "fake", "fake-model")), 1
    )
    response = await gateway.generate(REQUEST)
    assert response.input_tokens is None
    assert response.output_tokens is None


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["", "   ", "x" * (MAX_AI_OUTPUT_CHARS + 1)])
async def test_gateway_rejects_invalid_output(content: str) -> None:
    gateway = AIGateway(
        FakeProvider(ProviderResponse(content, "fake", "fake-model")), 1
    )
    with pytest.raises(AIProviderInvalidResponse) as caught:
        await gateway.generate(REQUEST)
    assert caught.value.latency_ms is not None


@pytest.mark.asyncio
async def test_gateway_enforces_hard_timeout() -> None:
    class SleepingProvider(FakeProvider):
        async def generate(self, _: AIRequest) -> ProviderResponse:
            await asyncio.sleep(1)
            return ProviderResponse("late", "fake", "fake-model")

    with pytest.raises(Exception) as caught:
        await AIGateway(SleepingProvider(), timeout_seconds=0.001).generate(REQUEST)
    assert getattr(caught.value, "code", None) == "AI_PROVIDER_TIMEOUT"


@pytest.mark.asyncio
async def test_gateway_preserves_neutral_provider_errors() -> None:
    with pytest.raises(AIProviderUnavailable) as caught:
        await AIGateway(FakeProvider(), timeout_seconds=1).generate(REQUEST)
    assert caught.value.latency_ms is not None
