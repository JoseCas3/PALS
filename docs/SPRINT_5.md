# Sprint 5 — AI-Assisted Practice Generation

## Objective

Generate structured candidate Questions for an existing Topic while preserving human approval and
the rule that only explicit Attempts can change Mastery.

## Delivered scope

- `POST /api/v1/topics/{topic_id}/question-generation`
- Strict request count 1–10 and `mixed | easy | medium | hard` difficulty
- Provider-neutral JSON Schema request mapped by the OpenAI Responses adapter
- Complete Pydantic validation with required answer references
- Textual duplicate detection without embeddings or semantic claims
- Transient frontend preview with visible answers and duplicate warnings
- “Use candidate” transfer to the existing editable Question form
- Metadata-only `AIInteraction` operation `question_generation`
- No candidate persistence, bulk approval, provenance, grading, or evidence mutation

## Validation and duplicate policy

The provider must return exactly the requested count. Candidate prompts are trimmed, nonblank, and
at most 1,000 characters; answer references are required, trimmed, nonblank, and at most 2,000.
Difficulty must be easy, medium, or hard and must match a specific requested mode. Any invalid field,
count mismatch, or normalized duplicate inside the result rejects the complete generation.

Prompt normalization is Unicode NFKC followed by trim, whitespace collapse, and casefold. Punctuation
remains significant. A match against an existing Question is returned with an advisory warning and
does not change ordinary Question creation semantics.

## Transactions and observability

The service loads context, commits a pending AIInteraction, calls the provider without an active
database transaction, and commits success or failure afterward. It stores provider/model, entity
references, prompt version, character/token counts, latency, request ID, and state only. Prompts,
academic text, provider bodies, and candidates are not retained.

Migration `20260912_04` makes `help_level` nullable and enforces Tutor levels 1–6 versus a null
generation level. Downgrade deletes generation observability rows that Sprint 4 cannot represent,
then restores Tutor-only constraints. It deletes no academic or evidence records.

## Grounding and safety

Generation uses Subject name, Topic name, optional Topic description, and model knowledge. It is not
grounded in uploaded course material. Generated answers may be inaccurate and must be reviewed.
Academic metadata and output are untrusted, context and output are bounded, provider errors are
sanitized, OpenAI uses `store=False` with zero retries, and the frontend renders plain text.

## Evidence isolation

Generation does not create Questions, Attempts, or Mastery; modify Exams or ExamTopic; grade answers;
or affect the deterministic Study Plan. A Question is created only when the user submits the existing
Question form. Mastery still changes only through successful explicit Attempt creation.

## Deferred

RAG, document ingestion, semantic duplicate detection, AI grading or verification, candidate
persistence, bulk approval, provenance, generation history, streaming, provider routing, background
jobs, authentication, billing, and analytics remain out of scope.
