from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingestion.extraction import ExtractedPage

_PARAGRAPH_BREAK = re.compile(r"\n{2,}")
_TOKEN = re.compile(r"\S+")
_SENTENCE_END = re.compile(r"[.!?][\"')\]]*$")


class ChunkingError(Exception):
    pass


@dataclass(frozen=True)
class ProcessedChunk:
    chunk_index: int
    text: str
    page_start: int
    page_end: int
    token_count: int


@dataclass(frozen=True)
class _Token:
    text: str
    page_number: int
    paragraph_end: bool = False
    sentence_end: bool = False


class LexicalTokenCounter:
    """Counts non-whitespace runs; these are neutral R2 lexical tokens."""

    def count(self, text: str) -> int:
        return len(_TOKEN.findall(text))


class DocumentChunker:
    def __init__(self, target_tokens: int, overlap_tokens: int) -> None:
        if target_tokens <= 0:
            raise ValueError("Chunk target must be positive")
        if overlap_tokens < 0 or overlap_tokens >= target_tokens:
            raise ValueError("Chunk overlap must be non-negative and smaller than target")
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.counter = LexicalTokenCounter()

    def chunk(self, pages: tuple[ExtractedPage, ...]) -> tuple[ProcessedChunk, ...]:
        tokens = self._tokens(pages)
        if not tokens:
            raise ChunkingError("Cannot chunk empty text")

        chunks: list[ProcessedChunk] = []
        start = 0
        while start < len(tokens):
            end = self._select_end(tokens, start)
            selected = tokens[start:end]
            text = " ".join(token.text for token in selected)
            chunks.append(
                ProcessedChunk(
                    chunk_index=len(chunks),
                    text=text,
                    page_start=min(token.page_number for token in selected),
                    page_end=max(token.page_number for token in selected),
                    token_count=self.counter.count(text),
                )
            )
            if end == len(tokens):
                break
            next_start = max(start + 1, end - self.overlap_tokens)
            if next_start >= end:
                next_start = end
            start = next_start
        return tuple(chunks)

    def _select_end(self, tokens: list[_Token], start: int) -> int:
        maximum = min(start + self.target_tokens, len(tokens))
        if maximum == len(tokens):
            return maximum
        minimum = start + max(1, self.target_tokens // 2)
        for boundary in ("paragraph_end", "sentence_end"):
            candidates = [
                index
                for index in range(minimum, maximum + 1)
                if getattr(tokens[index - 1], boundary)
            ]
            if candidates:
                return candidates[-1]
        return maximum

    @staticmethod
    def _tokens(pages: tuple[ExtractedPage, ...]) -> list[_Token]:
        tokens: list[_Token] = []
        for page in pages:
            for paragraph in _PARAGRAPH_BREAK.split(page.text):
                values = _TOKEN.findall(paragraph)
                for index, value in enumerate(values):
                    tokens.append(
                        _Token(
                            text=value,
                            page_number=page.page_number,
                            paragraph_end=index == len(values) - 1,
                            sentence_end=bool(_SENTENCE_END.search(value)),
                        )
                    )
        return tokens
