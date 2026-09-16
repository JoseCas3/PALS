from __future__ import annotations

import json

from app.ai.contracts import AIRequest, ProviderResponse


class FakeAIProvider:
    provider_name = "fake"

    def __init__(self, model_name: str = "fake-deterministic-v1") -> None:
        self.model_name = model_name

    async def generate(self, request: AIRequest) -> ProviderResponse:
        if (
            request.structured_response is not None
            and request.structured_response.schema_name == "grounded_question_tutor"
        ):
            content = json.dumps(
                {
                    "answer": "Use the supplied source evidence at the requested help level.",
                    "citations": ["S1"],
                }
            )
        else:
            content = "Use the requested help level to work through the question."
        return ProviderResponse(
            content=content,
            provider=self.provider_name,
            model=self.model_name,
            input_tokens=None,
            output_tokens=None,
            provider_request_id="fake-request",
        )
