from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Protocol

from app.ai.contracts import (
    AIProvider,
    AIProviderError,
    AIProviderException,
    AIProviderInvalidResponse,
    AIProviderTimeout,
    AIRequest,
    AIResponse,
)

MAX_AI_OUTPUT_CHARS = 12_000


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


class AIGateway:
    def __init__(self, provider: AIProvider, timeout_seconds: float) -> None:
        self.provider = provider
        self.timeout_seconds = timeout_seconds

    async def generate(self, request: AIRequest) -> AIResponse:
        started_at = perf_counter()
        try:
            async with asyncio.timeout(self.timeout_seconds):
                response = await self.provider.generate(request)
        except TimeoutError as exc:
            timeout_error = AIProviderTimeout(
                self.provider.provider_name, self.provider.model_name
            )
            timeout_error.latency_ms = _elapsed_ms(started_at)
            raise timeout_error from exc
        except AIProviderException as exc:
            exc.latency_ms = _elapsed_ms(started_at)
            raise
        except Exception as exc:
            provider_error = AIProviderError(
                self.provider.provider_name, self.provider.model_name
            )
            provider_error.latency_ms = _elapsed_ms(started_at)
            raise provider_error from exc

        latency_ms = _elapsed_ms(started_at)
        content = response.content.strip()
        if not content or len(content) > request.max_output_chars:
            invalid_error = AIProviderInvalidResponse(response.provider, response.model)
            invalid_error.latency_ms = latency_ms
            raise invalid_error
        return AIResponse(
            content=content,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            provider_request_id=response.provider_request_id,
            latency_ms=latency_ms,
        )


class AIGatewayResolver(Protocol):
    async def resolve(self) -> AIGateway: ...


class ResolvedAIGateway:
    def __init__(self, gateway: AIGateway) -> None:
        self.gateway = gateway

    async def resolve(self) -> AIGateway:
        return self.gateway
