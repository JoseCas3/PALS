from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import AIResponse
from app.models.ai_interaction import AIInteraction


class AIInteractionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_pending(self, **values: object) -> AIInteraction:
        interaction = AIInteraction(**values)
        self.session.add(interaction)
        await self.session.flush()
        await self.session.refresh(interaction)
        return interaction

    def finalize_success(
        self, interaction: AIInteraction, response: AIResponse
    ) -> None:
        interaction.provider = response.provider
        interaction.model = response.model
        interaction.output_chars = len(response.content)
        interaction.input_tokens = response.input_tokens
        interaction.output_tokens = response.output_tokens
        interaction.latency_ms = response.latency_ms
        interaction.provider_request_id = response.provider_request_id
        interaction.success = True
        interaction.error_code = None

    def finalize_failure(
        self, interaction: AIInteraction, *, error_code: str, latency_ms: int
    ) -> None:
        interaction.latency_ms = latency_ms
        interaction.success = False
        interaction.error_code = error_code

    async def get(self, interaction_id: uuid.UUID) -> AIInteraction | None:
        return await self.session.get(AIInteraction, interaction_id)
