# Sprint 0 — Foundation

## Objective
Create a reproducible local development environment.

## Deliverables
- monorepo structure
- README, .gitignore, .env.example
- FastAPI app
- PostgreSQL connection
- SQLAlchemy + Alembic
- /health and /ready
- pytest
- Next.js TypeScript app
- minimal home page
- API health status component
- Vitest
- docker-compose.yml
- GitHub Actions for backend/frontend checks

## Acceptance
docker compose up --build

must expose:
- Web: http://localhost:3000
- API docs: http://localhost:8000/docs

/health returns 200.
/ready returns 200 when PostgreSQL is reachable.

## Do not add
Auth, Redis, Celery, RAG, LLM integration, subjects/topics/exams or Kubernetes.
