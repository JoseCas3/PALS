from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    page_start: int
    page_end: int
    text: str
    relevance_score: float


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    sufficient: bool
