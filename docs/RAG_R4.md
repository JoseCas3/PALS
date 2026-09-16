# PALS R4 — Retrieval Service

## Status and scope

R4 is closed after implementation, independent review, and manual validation. It adds an internal-only
`RetrievalService`; it does not add an HTTP search endpoint, Tutor or Question Generation
integration, citation aliases, reranking, or an ANN index. Retrieval is evidence-neutral and has no
Attempt, Mastery, planner-evidence, or `AIInteraction` write path.

## Contract and query preparation

`RetrievalService.retrieve(subject_id, query, limit=None)` returns `RetrievalResult`, containing a
list of `RetrievedChunk` values and a deterministic `sufficient` boolean. Each returned chunk has
its chunk and Document IDs, original filename, page range, text, and relevance score. It never
contains an embedding, storage key, or filesystem path.

Query preparation applies Unicode NFC normalization, collapses whitespace runs to one ASCII space,
and rejects an empty result. The prepared query is embedded through the existing
`EmbeddingService -> EmbeddingProvider` path. Retrieval never imports a provider SDK or uses the
generative AI Gateway.

## Eligibility and exact ranking

The repository performs one PostgreSQL query joining `document_chunks` to `documents`. Its SQL
predicate requires the requested `Document.subject_id`, `READY` status, and exact equality with the
active embedding provider, model, and dimensions. Thus dimensions alone never establish
compatibility. A READY Document without chunks naturally contributes nothing.

Ranking uses pgvector's exact cosine distance expression, with no ANN index:

`relevance_score = 1 - cosine_distance`

Higher scores are better. Ordering is cosine distance ascending, Document UUID ascending,
`chunk_index` ascending, then chunk UUID ascending. The repository over-fetches up to four times
the requested final limit, bounded by `RETRIEVAL_MAX_LIMIT`, so thresholding and deduplication do
not usually undersize small result sets.

The service discards non-finite scores and scores below `RETRIEVAL_MIN_RELEVANCE`. The threshold is
inclusive: a score equal to the configured minimum survives. Deduplication then preserves the
first/best-ranked occurrence for an identity made by NFC-normalizing chunk text, collapsing
whitespace, and applying Unicode case folding. It never merges provenance; it simply omits later
duplicate identities. The first requested number of survivors is returned.

`sufficient` is true exactly when at least one eligible, threshold-surviving, deduplicated chunk is
returned. No compatible corpus and all-below-threshold candidates both return empty chunks with
`sufficient=false`; neither is an infrastructure error.

## Configuration and calibration

- `RETRIEVAL_TOP_K=8` selects the default final limit.
- `RETRIEVAL_MAX_LIMIT=50` bounds caller requests and candidate fetching.
- `RETRIEVAL_MIN_RELEVANCE=0.0` is an initial engineering default in the valid cosine-similarity
  range `[-1, 1]`.

The default threshold is deliberately not a scientific or product-quality calibration. It requires
empirical calibration during dogfooding with the production provider. `FakeEmbeddingProvider`
proves deterministic plumbing and vector ordering only; its hash-derived vectors provide no
evidence about semantic relevance or a production threshold.

## Infrastructure gate follow-ups

Malformed OpenAI response shapes are now normalized to the existing `EMBEDDING_FAILED` taxonomy.
Ingestion also catches ordinary unexpected embedding-stage exceptions, logs only safe identifiers
and exception class, clears derived chunks, and commits `FAILED` rather than leaving the Document
in `PROCESSING`. Cancellation and system-exit semantics are not caught.

Document and Subject deletion now stage each source PDF by an atomic same-filesystem move before
the database delete. A staging failure restores previously staged Subject files. A database flush
or commit failure rolls back and restores every staged file. After a successful commit, staged
files are finalized; a finalization failure leaves only an unreferenced staged orphan and is logged
without a path.

There remains a local process/host-crash window between staging and database commit: a crash can
leave live metadata whose PDF is in `.delete-staging` until manual recovery. A crash after commit
but before finalization can leave an orphan in staging. Eliminating both windows would require a
startup reconciliation protocol or distributed transaction machinery beyond R4; ordinary and
fault-injected failures are recoverable.
