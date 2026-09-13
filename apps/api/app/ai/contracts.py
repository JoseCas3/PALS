from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AIRequest:
    operation: str
    system_prompt: str
    user_prompt: str
    max_output_tokens: int


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    provider_request_id: str | None = None


@dataclass(frozen=True)
class AIResponse:
    content: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    provider_request_id: str | None
    latency_ms: int


class AIProvider(Protocol):
    provider_name: str
    model_name: str

    async def generate(self, request: AIRequest) -> ProviderResponse: ...


class AIProviderException(Exception):
    code = "AI_PROVIDER_ERROR"

    def __init__(self, provider: str, model: str) -> None:
        super().__init__(self.code)
        self.provider = provider
        self.model = model
        self.latency_ms: int | None = None


class AIProviderTimeout(AIProviderException):
    code = "AI_PROVIDER_TIMEOUT"


class AIProviderRateLimited(AIProviderException):
    code = "AI_PROVIDER_RATE_LIMITED"


class AIProviderUnavailable(AIProviderException):
    code = "AI_PROVIDER_UNAVAILABLE"


class AIProviderAuthenticationFailed(AIProviderException):
    code = "AI_PROVIDER_AUTHENTICATION_FAILED"


class AIProviderInvalidResponse(AIProviderException):
    code = "AI_PROVIDER_INVALID_RESPONSE"


class AIProviderError(AIProviderException):
    code = "AI_PROVIDER_ERROR"
