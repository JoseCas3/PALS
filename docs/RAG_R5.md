# PALS R5 — Grounded Tutor

## Status and boundary

**CLOSED**

R5 adds explicit REQUIRED grounding to the existing Question Tutor. The legacy ungrounded request
remains the default. R5 does not add a public Retrieval endpoint, grounded Question Generation,
citation persistence, a PDF viewer, highlighting, or other R6 citation UX. R6 now consumes the
authoritative R5 citation IDs without changing the R5 response contract.

Grounded Tutor, retrieval, AI generation, citation validation, and citation display are
evidence-neutral. None creates an Attempt or changes Mastery. Retrieval embeddings remain outside
`AIInteraction`; a successful or failed grounded generative call uses the existing metadata-only
`question_tutor` interaction lifecycle.

## Request and outcomes

`POST /api/v1/questions/{question_id}/tutor` accepts `help_level` and optional
`grounding_mode`. Omitting the mode preserves legacy `NONE`; R5 supports `REQUIRED`. The server
derives the Subject from Question → Topic → Subject, so callers cannot choose a conflicting
Subject.

The response adds typed `grounding_mode`, `outcome`, `answer`, and `citations` fields while retaining
the existing `content` field for compatibility. `ANSWER` has answer/content and, in REQUIRED mode,
at least one validated citation. `INSUFFICIENT_EVIDENCE` has no interaction, provider, model,
answer, or content and has an empty citation list.

## Pipeline

For REQUIRED mode, Tutor builds one deterministic query from Topic name and Question prompt and
calls `RetrievalService` once. An insufficient result returns the server-owned domain outcome
without creating an `AIInteraction` or invoking `AIGateway`. Retrieval infrastructure errors retain
embedding/database semantics and do not become insufficiency.

A sufficient ordered result becomes a transient `GroundedContext`. The server assigns aliases S1,
S2, and so on in retrieval order. Context contains only the returned chunk text, safe original
filename, and page range—never vectors, storage keys, or filesystem paths. The grounded prompt
retains the selected progressive-help ceiling and clearly marks all retrieved material as
untrusted quoted evidence rather than instructions. Delimiting untrusted data reduces prompt
injection risk but does not make prompt injection impossible.

Generation continues through `AIGateway` using a strict provider-neutral JSON Schema:

```json
{"answer": "Supported answer", "citations": ["S1"]}
```

The model supplies only answer text and aliases. It cannot supply authoritative UUIDs, filenames,
or pages.

## Citation validation and provenance

`CitationValidator` requires at least one alias, rejects empty or unknown aliases, and rejects the
entire grounded answer if any alias is invalid. Duplicate aliases are collapsed in model first-use
order. The validator maps every accepted alias back to its server-side `RetrievedChunk`, which is
the sole source of chunk ID, Document ID, filename, and page range. Aliases and citations are
response-scoped and are never persisted.

Malformed JSON, schema violations, empty citations, and fabricated aliases produce sanitized 502
`GROUNDING_INVALID_RESPONSE`. Provider timeouts, unavailability, authentication failures, and
invalid provider responses retain their existing 502/503/504 behavior.

## Outcome matrix

| Case | Result | Generative call |
|---|---|---:|
| Retrieval returns `sufficient=false` | 200 `INSUFFICIENT_EVIDENCE` | 0 |
| Retrieval infrastructure fails | Existing retrieval/application error | 0 |
| Retrieval succeeds; AI output and citations validate | 200 `ANSWER` | 1 |
| Retrieval succeeds; grounded output is invalid | 502 `GROUNDING_INVALID_RESPONSE` | 1 |
| Retrieval succeeds; provider fails | Existing provider error | 1 |

The deterministic fake AI adapter exists for local/E2E plumbing. The E2E environment also uses a
test-only `-1.0` retrieval threshold so hash-derived fake embeddings always exercise grounding.
Neither setting constitutes semantic-quality or production-threshold calibration.
