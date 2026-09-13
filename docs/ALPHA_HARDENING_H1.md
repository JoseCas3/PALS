# PALS Alpha 0.1 Hardening H1

## Scope

This remediation closes verified integration, safety, Docker, CI, and documentation gaps without
adding product features or changing the modular-monolith, evidence, Mastery, planner, or AI Gateway
architecture.

## Operation lifetime

- A successful Attempt always requests a Global Study Plan refresh.
- Returned Mastery is Topic-level evidence and is reconciled only when that Topic remains active.
- Attempt history, form reset, and success feedback are Question-specific and are published only
  when the initiating Question remains active.
- Question or Topic changes recover submitting state without cancelling a valid server write.
- Attempt history reads capture a write revision; a read started before a successful write cannot
  overwrite the post-write history.
- Academic mutations capture their initiating Subject and Exam. Successful writes may publish
  global academic/planner revisions, but stale records, forms, selections, and errors are suppressed.
- Exam plan selection changes invalidate old output and recover `generating` immediately.
- Tutor help-level controls are disabled while a request is active, so returned content cannot be
  mislabeled under a newly selected level.

## Persistence and error safety

Persisted Subject, Topic, Exam, and Question text rejects embedded NUL during request validation.
`time_spent_seconds` is bounded to PostgreSQL signed `INTEGER` range. SQLAlchemy engines hide SQL
parameters, and unexpected database failures are logged without exception text or bound values and
return the generic `DATABASE_ERROR` envelope. Raw database exceptions are never sent to clients or
stored in `AIInteraction`.

## Test database boundary

Backend tests require PostgreSQL and an explicit disposable database whose name ends in `_test`.
Alembic must upgrade that database before pytest. Test startup verifies required model tables and
columns and never calls `Base.metadata.create_all`, preventing tests from silently repairing an
omitted migration. CI runs `alembic check` after upgrade.

## Local-only deployment boundary

PALS Alpha is local-development software and must not be exposed as an unauthenticated public
service. Compose publishes PostgreSQL, API, web, and E2E API ports only on `127.0.0.1`.
Container-to-container networking remains unchanged.

## Dependency reproducibility

The frontend uses `package-lock.json`. Backend direct and development dependencies remain exactly
pinned in `pyproject.toml`. A transitive Python lock is deferred before Beta because introducing a
new resolver and update workflow would exceed this remediation's narrow scope.

## Deferred debt

ExamTopic request transport currently crosses a float boundary. The public numeric contract is not
changed in H1. Planner determinism over persisted Decimal values remains correct; decimal-safe API
transport is deferred to later API evolution.

## Regression assurance

Deferred-Promise frontend tests reproduce Attempt Question/Topic switches, stale history reads,
Exam assignment switches, Exam planner recovery, and Tutor selector interaction. Backend tests cover
NUL rejection, integer overflow, safe database responses/logging, and migration-only schema setup.
