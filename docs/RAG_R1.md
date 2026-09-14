# PALS RAG R1 — Document Domain

## Scope

R1 implements Subject-owned PDF upload, metadata persistence, deterministic listing, metadata get,
and hard deletion. PostgreSQL stores Document metadata; a configurable local filesystem stores the
PDF. New Documents have status `UPLOADED`.

R1 deliberately excludes extraction, normalization, chunks, embeddings, pgvector, retrieval,
grounding, citations, OCR, background work, and external storage.

## Implementation decisions

- Document identity is an application-generated UUID; content identity is lowercase SHA-256.
- `(subject_id, checksum_sha256)` and `storage_key` are database-unique.
- Storage keys are generated from the UUID and validated by construction; original filenames are
  metadata only.
- Local saves use a temporary file, flush and fsync it, then atomically replace the final path.
- A duplicate precheck avoids writes in the common case; the database constraint handles races and
  failed metadata persistence triggers best-effort cleanup.
- Document deletion removes the file before committing the row deletion. Subject deletion cleans
  all associated files before the existing valid Subject deletion transaction cascades metadata.
- R1 creates only `UPLOADED`; processing and embedding metadata remain unused and null.

## API

- `POST /api/v1/subjects/{subject_id}/documents` accepts multipart field `file` and returns 201.
- `GET /api/v1/subjects/{subject_id}/documents` returns an oldest-first Subject-scoped list.
- `GET /api/v1/documents/{document_id}` returns public metadata.
- `DELETE /api/v1/documents/{document_id}` returns 204 after deleting file and row.

Public responses omit `storage_key` and all physical paths. Errors use the standard PALS envelope
with `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`, `INVALID_PDF`, `DOCUMENT_ALREADY_EXISTS`,
`DOCUMENT_NOT_FOUND`, or `DOCUMENT_STORAGE_ERROR`.

## Configuration and persistence

- `DOCUMENT_STORAGE_ROOT` defaults to `./data/documents` outside Docker and
  `/var/lib/pals/documents` in Docker Compose.
- `DOCUMENT_MAX_SIZE_BYTES` defaults to `26214400` (25 MiB).
- Docker Compose mounts the named `document_data` volume at the storage root.
- Backend tests use pytest temporary directories; E2E storage uses disposable tmpfs.

## Migration

Alembic revision `20260913_05`, based on `20260912_04`, creates only `documents`, its checks,
foreign key, unique constraints, and `(subject_id, created_at, id)` index. The Subject foreign key
uses `ON DELETE CASCADE`. No chunk table, vector column, or extension is added.

## Test coverage

PostgreSQL-backed tests cover valid persistence, opaque storage, public-path privacy, configurable
limits, extension/MIME/signature validation, duplicate permutations, Subject scoping, get/not-found,
file and row deletion, evidence isolation, Subject cascade cleanup, hostile filenames, database
failure cleanup, and storage failure behavior.

Vitest covers empty/loading/list states, upload and safe errors, deletion, and deferred-Promise
Subject-switch protection for list, upload, and delete outcomes. Playwright covers a real no-AI-key
upload, UI display, reload persistence, and deletion against disposable PostgreSQL/FastAPI/Next.js.

## Deferred items

R2+ owns extraction, normalization, chunks, processing/retry APIs, embeddings, pgvector, retrieval,
Tutor grounding, Question Generation grounding, and citations. OCR, semantic chunking, external
vector databases, workers, Redis, Celery, cloud object storage, authentication, Study Sessions,
richer Question types, and spaced repetition remain out of scope.
