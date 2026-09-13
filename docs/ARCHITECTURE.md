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

## Sprint 4 AI flow

Sprint 4 realizes the provider boundary as `TutorService -> AIGateway -> AIProvider ->
OpenAIProvider`. Only the adapter imports the OpenAI SDK. The model comes from configuration and
no vendor type crosses the adapter boundary.

TutorService reads Question/Topic/Subject context, commits a pending metadata-only AIInteraction,
then calls the provider with no database transaction open. A short second transaction finalizes
success or failure. TutorService has no dependency on Attempt, Mastery, ExamTopic, or planner
mutation paths.

## Sprint 5 Question generation flow

Sprint 5 adds `QuestionGenerationService -> AIGateway -> AIProvider -> OpenAIProvider` alongside
Tutor. A dedicated read repository loads Subject/Topic metadata and existing Question prompts. Only
the metadata is sent to the provider; existing prompts remain local for textual duplicate checks.

`AIRequest` optionally carries a provider-neutral JSON Schema description and an operation-specific
output-character limit. The OpenAI adapter maps that description to strict Responses API structured
output, while the service parses the returned JSON and applies authoritative Pydantic and domain
validation. Candidates are returned to the browser and are not persisted. Approval continues through
`QuestionService`; generation has no dependency on evidence or planner mutation paths.

## Sprint 6 global planning flow

Sprint 6 extends the existing planner service rather than creating a parallel planning subsystem.
The Exam-specific and Global planners share one pure scoring operation over Mastery, Exam date,
ExamTopic weight, and the captured UTC instant, preventing formula and precision drift.

The Global route captures time once. One repository query joins active Exam, Subject, ExamTopic,
Topic, and optional Mastery rows. The service maps absent Mastery to virtual zero, scores each
ExamTopic independently, and applies the authoritative cross-Exam ordering in memory. Database
return order is irrelevant and no per-Exam or per-Topic query is issued.

Global planning contains no write, lock, commit, AI, Question, Attempt, or AIInteraction path. The
queue is returned on demand with `Cache-Control: no-store`; no plan or recommendation is stored.

## Sprint 7 frontend coordination

`LearningWorkspace` is the narrow coordination boundary for cross-panel UI state. It owns the
selected Practice Subject/Topic IDs plus monotonic academic and planner revisions. DomainManager,
PracticeManager, and both planners retain their entity lists, forms, requests, and domain-specific
state.

Global planner actions and DomainManager Topic selection call one typed parent operation that sets
Subject and Topic atomically. A Subject-only change clears Topic. Exam identity is deliberately not
part of Practice context. Selection is not persisted or encoded in the URL.

Practice requests and writes capture their initiating Topic, Question where applicable, and context
generation. Valid backend writes finish normally, but delayed results or errors cannot mutate a
newer UI context. A successful Attempt always advances the planner revision even if the user has
already navigated elsewhere because its persisted evidence remains authoritative.
