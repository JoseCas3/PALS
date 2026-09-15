from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO, Protocol

from pypdf import PdfReader


class TextExtractionError(Exception):
    pass


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    pages: tuple[ExtractedPage, ...]


class DocumentExtractor(Protocol):
    def extract(self, source: BinaryIO) -> ExtractedDocument: ...


class PypdfDocumentExtractor:
    def extract(self, source: BinaryIO) -> ExtractedDocument:
        try:
            reader = PdfReader(BytesIO(source.read()), strict=True)
            pages = tuple(
                ExtractedPage(page_number=index, text=page.extract_text() or "")
                for index, page in enumerate(reader.pages, start=1)
            )
        except Exception as exc:
            raise TextExtractionError("PDF text extraction failed") from exc
        return ExtractedDocument(pages=pages)
