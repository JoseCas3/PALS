# Sprint 1 â€” Domain Core

## Objective

Introduce the academic structure used by later PALS capabilities: Subjects, Topics, Exams, and
weighted ExamTopic associations.

## Delivered scope

- PostgreSQL schema and first Alembic domain migration
- Async SQLAlchemy models, explicit repositories, and domain services
- CRUD APIs under `/api/v1`
- Same-subject ExamTopic enforcement and idempotent weight upsert
- Restrictive academic-entity deletion
- PALS error envelopes for domain and request validation errors
- Explicit CORS support for GET, POST, PATCH, PUT, and DELETE
- Minimal Next.js management UI
- PostgreSQL integration and frontend component tests

## Domain rules

- Names are trimmed and may not be blank.
- Topic and Exam Subject ownership cannot be changed.
- Exam dates must be timezone-aware, are normalized to UTC, and may be historical.
- ExamTopic weight must satisfy `0 < weight <= 1`.
- Exam and Topic must belong to the same Subject.
- ExamTopic weights are not required to sum to 1.

## Deletion

- An empty Subject can be deleted.
- A Subject with Topics or Exams returns 409.
- An unassigned Topic can be deleted.
- A Topic assigned to an Exam returns 409.
- Deleting an Exam cascades only to its ExamTopic rows and never to Topics.

## Local migrations

Docker Compose runs `alembic upgrade head` before starting Uvicorn solely as a local development
convenience. It does not define a future production deployment strategy.

## Deferred

Authentication, topic dependencies, questions, attempts, mastery, planning, AI, RAG, Redis,
workers, uploads, notifications, analytics, and production deployment remain out of scope.
