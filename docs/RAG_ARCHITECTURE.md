# PALS Post-Alpha RAG Architecture

## Purpose and non-goals

The Post-Alpha RAG track will let PALS use a learner's Subject-owned course documents as grounded
study context. R1 establishes durable Document identity, metadata, validation, local storage, and
lifecycle states; R2–R6 incrementally add processing, embeddings, retrieval, grounded Tutor, and
usable citation navigation while preserving the frozen boundaries below.

PALS remains a single-user, local-first modular monolith with Next.js, FastAPI, PostgreSQL, and a
local filesystem. It does not add authentication, network object storage, a vector database,
Redis, workers, or a microservice boundary.

## Evidence authority invariant

A successfully committed Attempt creation remains the only operation allowed to change Mastery.
Document upload, listing, inspection, deletion, future processing, retrieval, Tutor grounding, and
grounded Question Generation must never create Attempts or mutate Mastery. Existing deterministic
planners remain read-only projections. AIInteraction remains metadata-only.

## Module boundaries and ownership

A Document belongs directly to one Subject and never directly to a Topic. The Document HTTP route
delegates business and transaction rules to `DocumentService`, which uses `DocumentRepository` for
PostgreSQL metadata and `DocumentStorage` for bytes. Storage resolution is private to the storage
implementation; routes and public schemas never receive physical paths.

The AI Gateway remains the generative provider boundary. R3 embeddings use the separate
provider-neutral `EmbeddingProvider` and `EmbeddingService`; OpenAI SDK details remain inside the
embedding adapter and never enter ingestion, retrieval, Tutor, or Question Generation modules.

## Local storage strategy

PostgreSQL stores metadata and an opaque key such as `<uuid-prefix>/<uuid>.pdf`; it never stores PDF
bytes or absolute host paths. `LocalDocumentStorage` resolves validated opaque keys under the
configured `DOCUMENT_STORAGE_ROOT` and implements `save`, `open`, `delete`, and `exists`. Original
filenames are display metadata only and cannot select a destination path.

Docker mounts a named volume at the configured storage root. Backend tests override storage with a
per-test temporary directory, and E2E uses disposable tmpfs storage. No file server exposes the
storage root.

## Upload lifecycle and identity

Upload validates a present filename, `.pdf` extension, supplied `application/pdf` MIME type, the
configured byte limit, non-empty content, and the `%PDF-` signature. SHA-256 is calculated from the
binary content. A UUID determines the domain identity and opaque storage key.

The pair `(subject_id, checksum_sha256)` is unique: identical bytes in one Subject are rejected,
while the same filename with different bytes and the same bytes in different Subjects are allowed.
After validation and a duplicate precheck, storage writes a temporary file and atomically renames
it to the final key. Metadata is then inserted and committed. Storage failure creates no row; a
database failure after storage triggers best-effort removal. A process crash in that narrow gap may
leave an orphan file and is accepted R1 debt.

Deleting a Document removes its physical file and metadata row. Subject deletion remains blocked
by existing Topic or Exam rules; when otherwise valid, it removes Subject Document files and lets
the database cascade their rows. No Document operation touches Questions, Attempts, Mastery,
AIInteraction, or planner inputs.

R2 processing reads through `DocumentStorage`, extracts immutable one-based page values through a
library-neutral `DocumentExtractor`, normalizes each page with deterministic NFC-based rules, and
produces transient page-aware lexical-token chunks. Blocking parsing runs outside the event loop
and outside a database transaction. R3 embeds the complete transient chunk set outside a database
transaction, then atomically replaces derived chunks and publishes one embedding profile with
READY. PostgreSQL owns chunks through a cascading foreign key; pgvector stores fixed 1,536-value
vectors. No similarity endpoint or ANN index exists in R3.

## R1-R3 status semantics

The controlled statuses are `UPLOADED`, `PROCESSING`, `READY`, and `FAILED`. R1 creates only
`UPLOADED`; processing atomically claims work and records READY or FAILED. R3 READY means a complete
persisted chunk set with validated embeddings and matching Document profile metadata. An R2 READY
row with null embedding metadata and zero chunks can be explicitly processed once for upgrade; no
migration or startup path calls an embedding provider.

## Future extraction, chunks, embeddings, and retrieval

R2 adds synchronous PDF text extraction, deterministic normalization, and transient chunks without
OCR. R3 adds DocumentChunk records with stable ordering and provenance plus a provider-neutral
embedding service and PostgreSQL pgvector storage; PALS does not use an external vector database.
R4 implements internal Subject-scoped exact cosine retrieval, exact embedding-profile eligibility,
centralized thresholds and limits, deterministic deduplication, stable ordering, explicit
sufficiency, and provenance-preserving result values. R5 lets explicit REQUIRED Question Tutor
requests consume retrieval through server-issued aliases and validated response-level citations;
Question Generation remains ungrounded. R6 consumes those provenance IDs through an exact
READY-Document evidence lookup and `/documents/{document_id}?chunk={chunk_id}` UI route. Aliases
remain transient, source text is rendered as untrusted plain text, and neither the endpoint nor UI
invokes retrieval or AI. See `RAG_R4.md`, `RAG_R5.md`, and `RAG_R6.md`.

Processing remains synchronous initially. Workers are deferred until measured workload requires
them. OCR, semantic chunking, external vector stores, S3/MinIO, LangChain, LlamaIndex, and
Unstructured are outside the frozen architecture.

## R2-R7 roadmap

1. R2: deterministic PDF extraction, normalization, transient chunking, and lifecycle transitions.
2. R3: persisted chunks, embeddings, pgvector, and atomic retrieval-ready publication.
3. R4: Subject-scoped retrieval with deterministic filtering and thresholds (closed).
4. R5: grounded Tutor context and source citations without changing evidence authority (closed).
5. R6: citation navigation and Document evidence UX (closed).
6. R7: end-to-end RAG hardening (implemented; pending independent review).

Each sprint must preserve local-first operation, provider isolation, metadata-only AIInteraction,
and the rule that only successful Attempt creation changes Mastery.

R7's lifecycle, recovery, crash-window, privacy, dependency-debt, and integrated validation record
is documented in `RAG_R7.md`.
