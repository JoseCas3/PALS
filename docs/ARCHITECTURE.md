# PALS Architecture

## Style
Modular monolith.

## High level
Browser → Next.js → FastAPI → PostgreSQL

FastAPI modules:
- subjects
- topics
- exams
- questions
- attempts
- mastery
- planner
- AI

## Backend layers
API routes → services → repositories → database

Routes must not contain business logic beyond validation/orchestration.

Sprint 1 implements these layers as explicit packages under `apps/api/app`:
- `api/v1`: versioned HTTP routes and response mapping
- `schemas`: Pydantic request and response validation
- `services`: domain rules and transaction boundaries
- `repositories`: entity-specific SQLAlchemy queries
- `models`: SQLAlchemy persistence models

Repositories do not commit independently. Services coordinate each write in one transaction.
The ExamTopic same-subject invariant is enforced by its service; database foreign keys and the
composite primary key provide referential and duplicate protection.

## AI dependency rule
Business modules must not import vendor SDKs directly.

Correct:
business service → AI service interface → provider adapter

## Configuration
Secrets come from environment variables.

## Deferred infrastructure
Redis, workers, object storage and vector search are added only when a concrete feature requires them.
