# PALS RAG R2 - Deterministic PDF Ingestion

## Scope

R2 adds local page-preserving PDF text extraction, conservative deterministic normalization,
deterministic transient chunking, and the Document processing lifecycle. It does not persist
extracted text or chunks and does not implement embeddings, pgvector, retrieval, grounding,
citations, or OCR.

## Extraction dependency and boundary

Production extraction uses `pypdf==6.18.1` behind the library-neutral `DocumentExtractor`
protocol. pypdf is a maintained, pure-Python parser with page-by-page text extraction and Python
3.14 support. It is licensed BSD-3-Clause according to the project's LICENSE and PyPI metadata,
so it avoids PyMuPDF's AGPL/commercial constraint. No second parser or external service is used.

`PypdfDocumentExtractor` returns only immutable `ExtractedDocument` and `ExtractedPage` values.
Page numbering is human-oriented and begins at 1. Empty individual pages are preserved. Parser
objects and exceptions never cross the extractor boundary.

## Normalization

Each page is normalized independently using Unicode NFC. CRLF and CR become LF, NUL characters
are removed, horizontal whitespace runs become one space, line-trailing whitespace is removed,
three or more consecutive newlines become two, and outer whitespace is trimmed. The rules are
idempotent and do not summarize, reorder, translate, or heuristically remove content.

After normalization, a document must contain at least 32 non-whitespace characters across all
pages. A successfully parsed document below that centrally defined threshold fails with
`TEXT_EXTRACTION_INSUFFICIENT`. OCR is not attempted.

## Counting and chunking

R2 defines one lexical token as a non-whitespace run. These are not OpenAI tokens and are
independent of future embedding providers. Defaults are 800 target lexical tokens and 120 overlap
tokens, configured through `RAG_CHUNK_TARGET_TOKENS` and `RAG_CHUNK_OVERLAP_TOKENS`. Target must be
positive; overlap must be non-negative and smaller than target.

The chunker prefers the latest paragraph boundary in the latter half of the target window, then a
sentence-ending boundary, then the hard target lexical-token boundary. Overlap is a bounded suffix
of the preceding chunk. Chunk indexes begin at 0. Every chunk records inclusive one-based
`page_start` and `page_end`; multi-page chunks and overlap retain the provenance of every included
token. The transient output contains no UUID.

## Lifecycle and retry

`POST /api/v1/documents/{document_id}/process` atomically claims only `UPLOADED` or `FAILED`
documents with one PostgreSQL conditional update. The PROCESSING state is committed before the
storage file is opened and before blocking extraction runs in a worker thread, so no database
transaction spans parsing. Success records READY and clears `error_code`; failure records FAILED
with a safe current error code. FAILED retries use the same endpoint. PROCESSING and READY requests
are rejected with safe conflict errors.

READY in R2 means only that extraction, normalization, and transient chunking succeeded. Retrieval
must continue to ignore this state until R3 extends publication to atomically persist chunks and
embeddings.

## Privacy and errors

Processing reads the PDF only through `DocumentStorage.open`. It never reconstructs a path from a
filename or storage key. PDF bytes, page text, normalized text, chunks, paths, and parser payloads
are not logged or returned. Operational logs contain only document identity, counts, and safe
exception class metadata. Safe failure codes are `TEXT_EXTRACTION_FAILED`,
`TEXT_EXTRACTION_INSUFFICIENT`, `CHUNKING_FAILED`, and `PROCESSING_FAILED`.

## Tests and deferred work

Backend tests cover extraction, one-based page provenance, empty pages, malformed input,
normalization and idempotence, boundary priority, overlap, pathological input, configuration,
lifecycle transitions, retry, failure mapping, storage failure, transaction lifetime, and evidence
isolation. Frontend tests cover lifecycle UX and deferred-promise race protection. Playwright uses
synthetic PDFs with the real parser and no AI key.

R3+ owns persisted DocumentChunk rows and UUIDs, embeddings, pgvector, atomic retrieval-ready
publication, retrieval, grounding, and citations. OCR, semantic chunking, workers, Redis, and cloud
storage remain deferred.
