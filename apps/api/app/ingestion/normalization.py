import re
import unicodedata

from app.ingestion.extraction import ExtractedPage

_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\n]+")
_EXCESSIVE_BLANK_LINES = re.compile(r"\n{3,}")


class TextNormalizer:
    def normalize(self, text: str) -> str:
        normalized = unicodedata.normalize("NFC", text)
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        normalized = normalized.replace("\x00", "")
        lines = [
            _HORIZONTAL_WHITESPACE.sub(" ", line).rstrip()
            for line in normalized.split("\n")
        ]
        normalized = "\n".join(lines)
        return _EXCESSIVE_BLANK_LINES.sub("\n\n", normalized).strip()

    def normalize_pages(self, pages: tuple[ExtractedPage, ...]) -> tuple[ExtractedPage, ...]:
        return tuple(
            ExtractedPage(page_number=page.page_number, text=self.normalize(page.text))
            for page in pages
        )
