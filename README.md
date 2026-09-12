# PALS — Personal Adaptive Learning System

PALS is a personal adaptive learning platform designed to answer:

> What should I study now, and am I actually learning it?

## Alpha 0.1 goal
- Create subjects
- Create topics/subtopics
- Create exams
- Ask a contextual AI tutor
- Generate questions
- Record attempts
- Update topic mastery
- Display basic progress

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

Domain integration tests require PostgreSQL and use `DATABASE_URL`. With the Compose
database running, the default host URL works:

```bash
docker compose up -d postgres
cd apps/api
python -m pytest
```
