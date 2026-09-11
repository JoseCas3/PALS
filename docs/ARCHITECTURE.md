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

## AI dependency rule
Business modules must not import vendor SDKs directly.

Correct:
business service → AI service interface → provider adapter

## Configuration
Secrets come from environment variables.

## Deferred infrastructure
Redis, workers, object storage and vector search are added only when a concrete feature requires them.
