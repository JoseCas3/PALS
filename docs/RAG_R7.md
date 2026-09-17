# PALS R7 — Integration Hardening

## Status and scope

**CLOSED — INDEPENDENTLY REVIEWED**

The later RAG milestone architecture review accepted the architecture with bounded follow-ups.
Those follow-ups are recorded separately in `RAG_STABILIZATION_S1.md`; this historical R7 hardening
record remains otherwise unchanged.

R7 audits and hardens the integrated R1–R6 retrieval-augmented Tutor flow. It adds no product
feature, endpoint, table, migration, provider, framework, worker, queue, authentication boundary,
OCR, PDF viewer, citation persistence, chunk browser, or ANN index. Question Generation remains
outside RAG. The local-first modular-monolith architecture and synchronous processing boundary are
unchanged.

## Integrated lifecycle

The authoritative flow is:

1. Upload validates PDF bytes, atomically saves the file, and commits an `UPLOADED` Document.
2. Processing atomically claims `UPLOADED` or `FAILED` as `PROCESSING`. The only legacy exception is
   an R2 `READY` row with null profile metadata and no chunks.
3. Extraction, normalization, chunking, and all embedding calls run without an open database
   transaction.
4. One short transaction replaces derived chunks and changes the Document to `READY` with the exact
   embedding provider, model, and dimensions.
5. Any processing failure rolls back publication, removes derived chunks, and marks the claimed row
   `FAILED`. A later retry replaces rather than appends chunks.
6. Retrieval uses exact cosine search over only the requested Subject's `READY` Documents whose
   provider, model, and dimensions match the active query profile.
7. REQUIRED grounded Tutor either returns structured insufficiency without generation, or validates
   at least one server-issued citation alias and maps provenance exclusively from retrieved chunks.
8. Exact evidence inspection requires the cited Document/chunk pair and a still-`READY` Document.
9. Document deletion stages the file, commits cascading metadata deletion, then finalizes the staged
   file deletion. Old retrieval and evidence targets are unavailable after commit.

## Concurrency and recovery

The PostgreSQL conditional update is the processing mutex. Exactly one concurrent claimant can move
an eligible Document to `PROCESSING`; other claimants receive a deterministic conflict. Chunks are
not published until the complete vector set is validated, and the chunk replacement plus `READY`
profile update commit atomically.

R7 closes a process/delete race at failure cleanup. If deletion commits after processing is claimed,
publication fails safely and cleanup now treats the absent Document as deletion winning the race.
The caller receives the sanitized `PROCESSING_FAILED` application error; no Document or chunk can
reappear. Cleanup still raises and rolls back if a row exists in an unexpected non-`PROCESSING`
state, so the tolerance does not hide lifecycle corruption.

Delete rollback restores staged files when database deletion fails. A finalization failure after a
successful database commit can leave a private staging orphan, but cannot expose a stale Document or
evidence row. Subject deletion uses the same stage/restore/finalize discipline for every Document.

## Crash-window classification

| Window | Classification | Consequence / recovery |
| --- | --- | --- |
| File save committed, metadata insert not committed | Bounded accepted limitation | A process crash can leave an unreferenced private file; ordinary database errors invoke best-effort cleanup. |
| `PROCESSING` claim committed, process terminates before FAILED/READY | Bounded accepted limitation | The row can remain `PROCESSING`; no worker/watchdog was added. Manual operational recovery is required. |
| Extraction/embedding failure while process remains alive | Currently recoverable | No provider transaction is held; cleanup commits `FAILED` with zero chunks and retry is allowed. |
| Chunk replacement/profile publication failure | Currently recoverable | One database rollback removes partial publication, then cleanup commits `FAILED`. |
| Document delete database failure after file staging | Currently recoverable | The transaction rolls back and the staged file is restored. |
| Delete commit succeeds, staging finalization fails | Bounded accepted limitation | Metadata and chunks stay deleted; a private staged orphan may require maintenance cleanup. |
| Process and delete overlap | Currently recoverable | Either READY publication or deletion wins; committed state cannot be a corrupted READY row. |
| Retrieval and delete overlap | Currently recoverable | A transaction may return a pre-delete snapshot, but no stale retrievable/evidence state persists after delete commit. |

No reproducible persistent state-corruption window was found.

## Trust, privacy, and evidence authority

Embeddings remain behind the provider-neutral `EmbeddingProvider`/`EmbeddingService` boundary. The
OpenAI SDK appears only in its adapter. Provider responses must have exact cardinality, stable
indexes, 1,536 finite numeric values, and the configured model profile. Missing credentials do not
prevent startup and fail provider use with a sanitized unavailable error. Tests use no real provider
credentials.

Retrieval is internal only. There is no public search route or generic chunk listing route. Public
responses and safe logs do not expose embeddings, storage keys, physical paths, credentials, raw
provider payloads, prompts, or full Documents. Source text and filenames are untrusted and render as
escaped plain text. Prompt-injection-like source content cannot choose aliases or provenance IDs.

Only successful Attempt creation changes Mastery. Upload, processing, embeddings, retrieval,
grounded help, citation validation, evidence viewing, and deletion create no Attempt and do not
modify Mastery. AIInteraction remains metadata-only and is created only when a generative Tutor call
is actually attempted; embedding, retrieval, insufficiency, and evidence viewing create none.

## Database assessment

`document_chunks.embedding` remains PostgreSQL `VECTOR(1536)`. Document ownership uses cascading
foreign keys; `(document_id, chunk_index)` is unique; page ranges and token counts are constrained;
Document status/profile fields remain controlled. Exact scan is intentional at local scale, so no
HNSW or IVFFlat index exists. R7 requires no schema or migration change.

## Dependency and pre-Beta debt

JavaScript transitive dependencies are locked by `package-lock.json`. Python direct production and
development dependencies are exactly pinned in `pyproject.toml`, but there is no authoritative
transitive Python lock. Introduce and validate a reproducible lock workflow before Beta; R7 does not
select a resolver or alter dependencies.

`ExamTopic.weight` still crosses the public Pydantic transport boundary as `float`, while persisted
and planner calculations use exact decimal behavior. Decimal-safe API transport remains explicit
pre-Beta debt and is untouched because it is outside RAG integration hardening.

Semantic relevance threshold calibration remains deferred. The deterministic fake embedding
provider proves contracts and isolation, not retrieval quality.

## Validation ownership

R7 integration coverage adds real PostgreSQL tests for concurrent processing claims and deletion
during in-flight processing. The existing R1–R6 suites continue to own exhaustive processing failure
atomicity, FAILED retry, legacy upgrade, profile filtering, Subject isolation, READY filtering,
grounded insufficiency, adversarial citations, exact cross-Document evidence rejection, missing
credentials, non-exposure, evidence neutrality, and browser citation navigation.
