# PALS R3 — Embeddings and pgvector

## Scope and versions

R3 turns deterministic R2 chunks into a persistent retrieval substrate. PostgreSQL 17 runs the
pinned `pgvector/pgvector:0.8.6-pg17-bookworm` image, Alembic revision `20260915_06` installs the
`vector` extension, and Python uses `pgvector==0.5.0`. The migration downgrade removes only
`document_chunks`; it deliberately leaves the shared extension installed.

## Persistent chunk schema

`DocumentChunk` owns a UUID identity, cascading Document foreign key, zero-based chunk index, text,
one-based page range, positive token count, `VECTOR(1536)`, and creation time. Document and index
are unique together. Checks reject negative indexes, invalid page ranges, non-positive token counts,
and blank text. The only added index is the Document foreign-key lookup index; R3 adds no HNSW or
IVFFlat index.

## Embedding profile and boundaries

One installation has one active profile: `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`,
`EMBEDDING_DIMENSIONS`, and `EMBEDDING_BATCH_SIZE`. Defaults are `openai`,
`text-embedding-3-small`, 1,536, and a conservative batch size of 64. Configuration rejects any
other dimension because the schema is fixed. A future model or dimension change requires explicit
reprocessing/migration rather than invisible mixed spaces.

`EmbeddingProvider` is independent of the generative `AIGateway`. `EmbeddingService` batches
ordered texts and accepts a result only when cardinality, provider indexes, dimensions, numeric
types, and finite values all validate. It never returns a partial result. The OpenAI adapter uses
`AsyncOpenAI` and explicitly sends `dimensions=1536`; missing credentials fail processing safely as
`EMBEDDING_UNAVAILABLE` without preventing application startup. `FakeEmbeddingProvider` uses SHA-256
to create stable finite vectors and supports deterministic fault injection. Tests and E2E always
use fake embeddings and make no real API calls.

## Processing and atomic publication

Processing atomically claims an eligible Document and commits `PROCESSING`. File reading, PDF
extraction, normalization, chunking, and every embedding batch run with no database transaction
held open. Only after the entire vector set validates does one short transaction delete replaceable
derived rows, insert every chunk, set the Document embedding profile, clear errors, and set READY.
Any insert, READY update, or commit failure rolls the publication back; a separate short transaction
removes derived chunks and records FAILED with a safe code. Chunk text, vectors, provider payloads,
keys, and filesystem paths are not logged.

FAILED retries recompute and atomically replace rather than append; `(document_id, chunk_index)` is
the database safety net. A legacy R2 Document is upgradeable only when it is READY, has all three
embedding metadata fields null, and has zero chunks. A fully published R3 READY Document rejects
ordinary reprocessing. Document and Subject deletion retain R1 filesystem behavior, while the
foreign key cascades chunk deletion.

## Tests and invariants

Tests cover pgvector type/extension behavior, insert/read, wrong dimensions, constraints,
uniqueness, cascade, cosine distance, deterministic batching, malformed provider output, failures
at every batch position, transaction boundaries, atomic publication faults, retry, and legacy READY
upgrade. Document processing and embedding generation create no Attempts, change no Mastery,
Questions, Exams, ExamTopics, planners, or AIInteraction semantics.

R4 and later intentionally own retrieval, public search, query embeddings, grounding, citations,
ranking, thresholds, reranking, and any measured need for ANN indexes or workers. OCR, external
vector stores, multiple embedding spaces, Redis, Celery, LangChain, and LlamaIndex remain out of
scope.
