# PALS — Personal Adaptive Learning System

PALS is a personal adaptive learning platform designed to answer:

> What should I study now, and am I actually learning it?

## Alpha 0.1 goal
- Create subjects
- Create flat topics
- Create exams
- Ask a Question-scoped progressive AI tutor for six help levels
- Generate transient Question candidates for human review
- Record immutable, self-reported correctness Attempts
- Update topic mastery
- Generate deterministic per-Exam and Global Study Plans

PALS Alpha is local-development software. It is single-user and unauthenticated and must not be
exposed as a public service. Docker Compose publishes its host ports on `127.0.0.1` only.

## Initial stack
- Next.js + React + TypeScript + Tailwind CSS
- FastAPI + Python
- PostgreSQL
- SQLAlchemy + Alembic
- Pydantic
- Docker Compose
- pytest + Vitest
- GitHub Actions

## Source of truth
Before changing code, read:
1. docs/PRODUCT.md
2. docs/ARCHITECTURE.md
3. docs/DATABASE.md
4. docs/API.md
5. docs/AI.md
6. docs/DECISIONS.md

If a task conflicts with those documents, report the conflict instead of silently changing architecture.

## Sprint 0 development environment

The repository is a small monorepo:

- `apps/api`: FastAPI, SQLAlchemy async, Alembic, and pytest
- `apps/web`: Next.js, React, TypeScript, Tailwind CSS, and Vitest
- `docs`: product, architecture, and sprint specifications

### Prerequisites

- Docker with Docker Compose v2
- Git

Python 3.14 and Node.js 22 are provided by the development containers. They are only
required on the host when running checks outside Docker.

### Start the stack

Copy `.env.example` to `.env` if you want to customize ports or credentials. The checked-in
defaults work without an `.env` file.

```bash
docker compose up --build
```

The services are then available at:

- Web: http://localhost:3000
- API documentation: http://localhost:8000/docs
- Process health: http://localhost:8000/health
- Database readiness: http://localhost:8000/ready

`/health` only reports whether the API process is alive. `/ready` returns HTTP 200 when
PostgreSQL is reachable and HTTP 503 otherwise.

### Backend checks

From `apps/api`, with Python 3.14:

```bash
python -m pip install ".[dev]"
alembic upgrade head
alembic check
python -m pytest
python -m ruff check .
python -m mypy app tests
```

Alembic is configured for async SQLAlchemy. Sprint 0 intentionally contains no domain models
or migration revisions.

### Frontend checks

From `apps/web`, with Node.js 22:

```bash
npm ci
npm test
npm run lint
npm run typecheck
npm run build
```

The browser reads `NEXT_PUBLIC_API_URL` directly. `CORS_ORIGINS` is a comma-separated list of
the web origins allowed to make local API requests.

PDF uploads use persistent local storage. `DOCUMENT_STORAGE_ROOT` selects the storage root and
`DOCUMENT_MAX_SIZE_BYTES` sets the upload limit (25 MiB by default). Docker Compose stores files
in the named `document_data` volume, so normal container recreation does not remove them.
R2 processing uses `RAG_CHUNK_TARGET_TOKENS` (800 by default) and
`RAG_CHUNK_OVERLAP_TOKENS` (120 by default) for deterministic chunks. R3 publishes those chunks
with embeddings to PostgreSQL pgvector. The active profile defaults to OpenAI
`text-embedding-3-small`, 1,536 dimensions, and batches of 64; tests and E2E use the deterministic
fake provider. R4 adds internal Subject-scoped exact-cosine retrieval configured by
`RETRIEVAL_TOP_K` (8), `RETRIEVAL_MAX_LIMIT` (50), and `RETRIEVAL_MIN_RELEVANCE` (0.0). The initial
threshold is engineering plumbing, not production semantic calibration.
R5 adds explicit REQUIRED grounding to the existing Question Tutor, with structured insufficiency,
transient server-issued source aliases, validated response-level provenance, and no Mastery effect.
R6 adds interactive citations, exact READY source-evidence inspection, and a Document detail route;
the flow remains evidence-neutral and exposes no vectors or storage paths. See `docs/RAG_R5.md` and
`docs/RAG_R6.md`.
R7 hardens concurrency and process/delete recovery without adding product scope, and records the
integrated lifecycle, crash windows, and pre-Beta debt in `docs/RAG_R7.md`.
R6 and R7 are independently reviewed and closed. The milestone architecture review concluded
`RAG_MILESTONE=READY_WITH_FOLLOW_UPS`; bounded Stabilization S1 follow-ups are documented in
`docs/RAG_STABILIZATION_S1.md` and remain pending independent review.

## Sprint 1 domain core

Sprint 1 adds Subjects, Topics, Exams, and weighted ExamTopic associations under
`/api/v1`. The home page provides a minimal interface for managing these records.

The Docker Compose API command runs `alembic upgrade head` before Uvicorn as a local
development convenience. This is not the production migration strategy; production
migration orchestration remains a deployment concern for a later sprint.

To run migrations manually from `apps/api`:

```bash
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

Domain integration tests require PostgreSQL and use `DATABASE_URL`. The database must be an
explicit disposable database whose name ends in `_test`; tests refuse the normal `pals`
development database and never call `Base.metadata.create_all`. Apply Alembic first:

```bash
docker compose up -d postgres
cd apps/api
$env:DATABASE_URL="postgresql+asyncpg://pals:pals@localhost:5432/pals_test"
alembic upgrade head
alembic check
python -m pytest
```

## Sprint 2 practice evidence and mastery

Sprint 2 adds manually authored Questions, immutable self-reported Attempts, and exact
Topic Mastery scores. Mastery changes only when an Attempt and its corresponding Mastery
update commit together. The home page includes a minimal practice panel for selecting a
Topic, managing unattempted Questions, recording evidence, and reviewing recent Attempts.

Alpha correctness is self-reported. PALS does not automatically grade answers or use an AI
provider in Sprint 2. Mastery scores are stored as PostgreSQL `NUMERIC(5,2)` and returned as
fixed two-place strings.

## Sprint 3 adaptive study planner

Sprint 3 adds a deterministic, read-only Study Plan for an Exam at
`GET /api/v1/exams/{exam_id}/study-plan`. It ranks assigned Topics from exact Decimal
Mastery need, a linear 30-day Exam urgency, and ExamTopic weight, then explains which weighted
factor contributes most. Plans are calculated on demand and are never persisted. The home page
provides a minimal Subject-to-Exam planner that preserves the server ranking.

## Sprint 4 AI Gateway and Question Tutor

Sprint 4 adds question-scoped progressive Tutor help at levels 1 through 6 through a
provider-neutral AI Gateway and one OpenAI Responses API adapter. The configured model is not a
domain rule. Tutor output is plain text, non-streaming, and never changes Attempts, Mastery,
Questions, ExamTopic assignments, or Study Plans.

Tutor calls store metadata-only `AIInteraction` rows for operational observability. Prompts,
answer references, generated content, secrets, and provider payloads are not persisted. The API
still boots and all non-AI features work without `AI_API_KEY`; Tutor requests then return a safe
503 response.

## Sprint 5 AI-assisted practice generation

Sprint 5 adds Topic-scoped Question candidate generation at
`POST /api/v1/topics/{topic_id}/question-generation`. The AI Gateway requests a strict structured
result, PALS validates the complete result, and the frontend shows an unpersisted preview. A user
must copy one candidate into the ordinary editable Question form and submit the existing Question
endpoint before a Question is created.

Generation uses Subject and Topic metadata plus model knowledge; it is not grounded in uploaded
course material. Candidate prompts and answers are not retained by PALS. Generation never creates
Attempts or changes Mastery, ExamTopic data, or Study Plans. Without `AI_API_KEY`, both Tutor and
Question Generation return a safe 503 while non-AI features continue working.

## Sprint 6 global adaptive planner

Sprint 6 adds `GET /api/v1/study-plan`, a deterministic, read-only queue across every active
Exam and its assigned Topics. It reuses the Sprint 3 Decimal formula without cross-Exam
normalization: past Exams are excluded, an Exam exactly at the captured time is included, and the
same Topic appears once per ExamTopic obligation. The first server-ranked item is the current
recommendation. Plans remain calculated on demand, uncached, unpersisted, and independent of AI.

## Alpha workflow

1. Create a Subject.
2. Create a Topic.
3. Create a future Exam.
4. Assign the Topic to the Exam with a weight.
5. Review the Global Study Plan.
6. Choose **Practice this topic** on a recommendation.
7. Create or select a Question and record an explicit Attempt.
8. Observe the Mastery update and Global Study Plan reranking.

Sprint 7 keeps the selected Subject and Topic in browser memory, so a reload may reset the UI
selection. Academic data, Questions, Attempts, and Mastery remain persisted in PostgreSQL. Tutor and
Question Generation are optional: the deterministic workflow works with `AI_API_KEY` blank.

Run the browser-level Alpha flow against an isolated disposable database with:

```bash
cd apps/web
npm run test:e2e
```

## Post-Alpha RAG R1 document domain

R1 adds Subject-owned PDF Documents with PostgreSQL metadata and opaque-key local filesystem
storage. R2 adds explicit deterministic PDF extraction and page-aware chunking. R3 adds a separate
embedding boundary, pgvector 0.8.6, persistent `DocumentChunk` rows, atomic retrieval-ready
publication, the closed R4 Retrieval Service, closed R5 Grounded Tutor, closed R6 citation and
Document UX, and closed R7 integration hardening. The milestone architecture is accepted with the
bounded S1 follow-ups implemented pending independent review. See `docs/RAG_R1.md`,
`docs/RAG_R2.md`, `docs/RAG_R3.md`, `docs/RAG_R4.md`, `docs/RAG_R5.md`, `docs/RAG_R6.md`,
`docs/RAG_R7.md`, `docs/RAG_STABILIZATION_S1.md`, and `docs/RAG_ARCHITECTURE.md`.
