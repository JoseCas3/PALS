from __future__ import annotations

from typing import Any

import openai

from app.ai.contracts import (
    AIProviderAuthenticationFailed,
    AIProviderError,
    AIProviderInvalidResponse,
    AIProviderRateLimited,
    AIProviderTimeout,
    AIProviderUnavailable,
    AIRequest,
    ProviderResponse,
)


class OpenAIProvider:
    provider_name = "openai"

    def __init__(self, client: Any, model: str, timeout_seconds: float) -> None:
        self.client = client
        self.model_name = model
        self.timeout_seconds = timeout_seconds

    @classmethod
    def create(cls, *, api_key: str, model: str, timeout_seconds: float) -> OpenAIProvider:
        client = openai.AsyncOpenAI(
            api_key=api_key,
            max_retries=0,
            timeout=timeout_seconds,
        )
        return cls(client=client, model=model, timeout_seconds=timeout_seconds)

    async def aclose(self) -> None:
        await self.client.close()

    async def generate(self, request: AIRequest) -> ProviderResponse:
        try:
            response = await self.client.responses.create(
                model=self.model_name,
                instructions=request.system_prompt,
                input=request.user_prompt,
                max_output_tokens=request.max_output_tokens,
                store=False,
                timeout=self.timeout_seconds,
            )
            content = response.output_text
            if not isinstance(content, str) or not content.strip():
                raise AIProviderInvalidResponse(self.provider_name, self.model_name)
            usage = getattr(response, "usage", None)
            return ProviderResponse(
                content=content,
                provider=self.provider_name,
                model=str(getattr(response, "model", None) or self.model_name),
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                provider_request_id=getattr(response, "_request_id", None),
            )
        except AIProviderInvalidResponse:
            raise
        except openai.APITimeoutError as exc:
            raise AIProviderTimeout(self.provider_name, self.model_name) from exc
        except openai.RateLimitError as exc:
            raise AIProviderRateLimited(self.provider_name, self.model_name) from exc
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise AIProviderAuthenticationFailed(
                self.provider_name, self.model_name
            ) from exc
        except openai.APIConnectionError as exc:
            raise AIProviderUnavailable(self.provider_name, self.model_name) from exc
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise AIProviderUnavailable(
                    self.provider_name, self.model_name
                ) from exc
            raise AIProviderError(self.provider_name, self.model_name) from exc
        except Exception as exc:
            raise AIProviderError(self.provider_name, self.model_name) from exc
