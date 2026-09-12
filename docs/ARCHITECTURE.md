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

Sprint 2 follows the same layering for Questions, Attempts, and Mastery. `AttemptService` is
the sole mastery mutation path. It locks the Question, inserts the Topic Mastery row if absent,
locks Mastery with PostgreSQL `SELECT ... FOR UPDATE`, stages the Attempt and score update, and
commits once. This makes the evidence and projection atomic and prevents concurrent lost updates.

Question mutation and deletion use the same Question-first lock ordering as Attempt creation.
Once evidence exists, both operations return a conflict. Mastery reads before the first Attempt
return a virtual zero without inserting database state.

Sprint 3 implements the planner through a dedicated route, service, and repository. The service
loads the Exam, rejects historical planning, calculates urgency once, and obtains all Topic,
ExamTopic, and optional Mastery inputs with one joined query. Pure functions perform exact
Decimal calculations and deterministic sorting. The route captures one UTC instant through a
minimal injectable `utc_now` dependency and passes it explicitly to the service.

Study planning is a read-only projection: its path contains no add, flush, commit, delete,
`FOR UPDATE`, or Mastery lazy-insert operation. It does not persist plans or priorities. Within a
single Exam every Topic has the same urgency, so urgency changes absolute priority but cannot
change relative ordering; cross-Exam planning remains deferred.

## AI dependency rule
Business modules must not import vendor SDKs directly.

Correct:
business service → AI service interface → provider adapter

## Configuration
Secrets come from environment variables.

## Deferred infrastructure
Redis, workers, object storage and vector search are added only when a concrete feature requires them.
