# PALS RAG Stabilization S1 — Milestone Follow-up Hardening

## Status

**IMPLEMENTED — PENDING INDEPENDENT REVIEW**

The RAG milestone architecture review concluded `RAG_MILESTONE=READY_WITH_FOLLOW_UPS`. R6 and R7
are independently reviewed and closed. S1 implements only four bounded follow-ups: grounded prompt
budgeting, retrieval transaction lifetime, lazy Tutor generation composition, and truthful closure
documentation. It is not R8 and adds no product capability.

## F1 — Grounded prompt budget

Retrieval continues to return its configured ranked evidence without prompt concerns. Grounded
Tutor then deterministically considers that ordering as a prefix. For each candidate prefix it
assembles the exact grounded user prompt, including question context, evidence delimiters, filename,
pages, alias syntax, and closing instruction. The longest prefix whose assembled user prompt is at
most the existing 20,000-character maximum is selected. This exact assembly accounts for all
non-source overhead without a tokenizer or an approximate evidence-only allowance.

Evidence text is never truncated. Ordering is never changed. Final `S1`, `S2`, and later aliases are
assigned only after selection, so every authorized alias maps to one complete selected chunk and no
excluded chunk receives an alias. The selected chunk retains its exact chunk ID, Document ID,
filename, page range, text, and relevance score.

If the highest-ranked source alone cannot fit, the selected set is empty and REQUIRED grounding
returns the existing structured `INSUFFICIENT_EVIDENCE` outcome. It creates no generation call or
AIInteraction. The final 20,000-character prompt guard remains active as defense-in-depth and is not
increased or removed.

## F2 — Retrieval transaction lifetime

Previously, Subject validation and upstream Tutor context reads activated SQLAlchemy's transaction,
which stayed open during external query embedding. `RetrievalService` owns this orchestration
sequence and now rolls back the completed read-only prerequisite transaction after confirming the
Subject and before invoking the embedding provider. Rollback is intentional: it ends the read
transaction without acquiring authority to commit unrelated work. Query embedding therefore waits
with no active database transaction; the exact pgvector candidate query starts a new short
transaction afterward.

Repositories remain transaction-boundary neutral. Subject isolation, READY and embedding-profile
filters, exact cosine ordering, deduplication, threshold behavior, top-k, and explicit insufficiency
are unchanged.

## F3 — Lazy generative dependency

Question Generation continues to use the existing eager `AIGateway` dependency. Tutor now receives
a provider-neutral resolver whose construction performs no provider configuration check or SDK
initialization. `TutorService` resolves the gateway only after ordinary validation and, for REQUIRED
grounding, after retrieval is sufficient and at least one complete source fits the prompt budget.

Consequently, REQUIRED insufficiency succeeds even when generation is unconfigured. It returns no
answer, makes zero generation calls, and creates no AIInteraction, Attempt, or Mastery mutation.
REQUIRED grounding with sufficient selected evidence and `NONE` mode still resolve the gateway and
preserve the existing sanitized unavailable behavior. Provider-specific construction remains in API
composition; `TutorService` imports no provider SDK.

## Preserved boundaries

S1 adds no migration, table, column, index, endpoint, frontend feature, worker, queue, Redis,
external vector database, ANN, reranking, hybrid search, query rewriting, OCR, PDF viewer, grounded
Question Generation, citation persistence, auth, threshold calibration, dependency locking,
ExamTopic transport change, or recovery automation. PostgreSQL pgvector remains `VECTOR(1536)` and
exact cosine retrieval remains internal.

Only successful Attempt creation may modify Mastery. Upload, processing, embedding, retrieval,
Tutor help, citation viewing, and evidence viewing remain evidence-neutral.
