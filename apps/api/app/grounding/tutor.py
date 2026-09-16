from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.retrieval.contracts import RetrievedChunk


class GroundingValidationError(Exception):
    pass


@dataclass(frozen=True)
class GroundedSource:
    alias: str
    chunk: RetrievedChunk


@dataclass(frozen=True)
class GroundedContext:
    sources: tuple[GroundedSource, ...]

    @property
    def allowed_sources(self) -> dict[str, RetrievedChunk]:
        return {source.alias: source.chunk for source in self.sources}


@dataclass(frozen=True)
class GroundedCitation:
    alias: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    page_start: int
    page_end: int


def build_grounded_context(chunks: Sequence[RetrievedChunk]) -> GroundedContext:
    return GroundedContext(
        sources=tuple(
            GroundedSource(alias=f"S{index}", chunk=chunk)
            for index, chunk in enumerate(chunks, start=1)
        )
    )


class CitationValidator:
    def validate(
        self,
        allowed_sources: dict[str, RetrievedChunk],
        model_citations: Sequence[str],
    ) -> tuple[GroundedCitation, ...]:
        if not model_citations:
            raise GroundingValidationError("Grounded answer requires citations")
        seen: set[str] = set()
        validated: list[GroundedCitation] = []
        for alias in model_citations:
            if not alias or alias not in allowed_sources:
                raise GroundingValidationError("Grounded answer cited an unknown source")
            if alias in seen:
                continue
            seen.add(alias)
            chunk = allowed_sources[alias]
            validated.append(
                GroundedCitation(
                    alias=alias,
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    document_filename=chunk.document_filename,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                )
            )
        return tuple(validated)
