# PALS R6 — Citations and Document UX

## Status and boundary

**IMPLEMENTED — PENDING INDEPENDENT REVIEW**

R6 turns R5 response-level citation provenance into navigable study evidence. It adds an exact
Document/chunk evidence endpoint, interactive Tutor citation cards, and a Document detail route.
R6 does not add citation persistence, a generic chunk browser, retrieval/search endpoints, raw PDF
delivery, a PDF viewer, source coordinates, authentication, grounded Question Generation, or ANN.

Citation navigation and Document inspection are evidence-neutral. They never create Attempts,
modify Mastery, call AI, or run retrieval/embedding operations.

## Navigation and identity

A grounded Tutor citation links to:

```text
/documents/{document_id}?chunk={chunk_id}
```

The response-scoped alias remains display-only. `document_id` and `chunk_id` select the target;
filename, page range, status, and evidence text are always loaded from the backend. Client query
parameters cannot override provenance. Citation links open the normal Document route in a new tab
so the transient Tutor answer and active study workspace remain intact in the original tab.

The Subject Documents list also links to `/documents/{document_id}`. Without a chunk target, the
detail page shows safe Document metadata and explains that cited evidence is available only when
the page is opened from a Tutor citation. It never substitutes the first chunk or runs retrieval.

## Exact evidence endpoint

`GET /api/v1/documents/{document_id}/chunks/{chunk_id}` returns one exact READY evidence chunk:

```json
{
  "chunk_id": "...",
  "document_id": "...",
  "document_filename": "course.pdf",
  "page_start": 2,
  "page_end": 3,
  "text": "Exact cited excerpt"
}
```

The repository query requires both identifiers, `chunk.document_id == document_id`, an existing
Subject relationship, and `Document.status == READY`. A missing Document uses
`DOCUMENT_NOT_FOUND`; a missing, mismatched, or non-READY chunk uses the safe 404
`DOCUMENT_EVIDENCE_NOT_FOUND`. Deletion remains authoritative: cascading chunk deletion makes old
citation targets unavailable. The endpoint exposes no embedding, token metadata, storage key,
filesystem path, adjacent chunk, or full extracted Document.

PALS remains local, single-user, and unauthenticated. R6 enforces domain ownership/integrity but
does not claim user-level authorization that the product does not yet have.

## Document experience and trust boundary

The detail page separates Document metadata from “Source evidence,” labels page provenance as
`Page N` or `Pages N–M`, and describes the excerpt as source material rather than proof of answer
correctness. Loading, missing/deleted Document, missing evidence, malformed target, and general API
errors have explicit states. Citations and Document-list entries use semantic Next.js links with
useful accessible names and visible focus styling.

PDF-derived evidence and filenames are untrusted. React renders both as ordinary escaped text; the
UI uses no raw HTML or permissive Markdown rendering. Script- or HTML-like source content is shown
verbatim and cannot execute.

## R6/R7 boundary

R6 owns usable citation navigation and narrow source-evidence inspection. R7 may perform final RAG
integration hardening, but it must not reinterpret citation clicks or Document reading as learning
evidence. No migration, new table, index, provider configuration, or external service is required
for R6.
