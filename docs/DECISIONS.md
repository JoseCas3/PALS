# Architectural Decisions

## ADR-001 Modular monolith
Accepted.

## ADR-002 PostgreSQL
Accepted.

## ADR-003 FastAPI backend
Accepted.

## ADR-004 Next.js frontend
Accepted.

## ADR-005 Provider-agnostic AI boundary
Accepted.

## ADR-006 No authentication in Alpha 0.1
Accepted.

## ADR-007 No Redis/queue initially
Accepted.

## ADR-008 No RAG in Alpha 0.1
Accepted.

## ADR-009 Evidence-based mastery
Accepted. Reading explanations does not increase mastery.

## ADR-010 Sprint 1 restrictive academic deletion
Accepted. Subjects cannot be deleted while they have Topics or Exams, and Topics cannot be
deleted while assigned to Exams. Exam deletion cascades only through ExamTopic links.

## ADR-011 ExamTopic integrity
Accepted. `(exam_id, topic_id)` is the primary key, weight is greater than 0 and no greater than
1, and the same-subject invariant is enforced in the service layer without triggers.

## ADR-012 Exact deterministic mastery

Accepted. Mastery uses Python `Decimal`, PostgreSQL `NUMERIC(5,2)`, per-Attempt
`ROUND_HALF_UP`, and fixed two-place API strings. Help scales positive and negative evidence.

## ADR-013 Atomic and concurrency-safe evidence

Accepted. `AttemptService` stages Attempt and Mastery changes and commits once. Mastery rows are
created lazily with conflict-safe insertion and locked with `SELECT ... FOR UPDATE` to prevent
lost concurrent updates.

## ADR-014 Practice evidence preservation

Accepted. Attempts are immutable. Questions become immutable after their first Attempt.
Questions, Attempts, and Mastery use restrictive foreign keys; no practice evidence is deleted
through a cascade. Topic deletion is blocked by Questions or learning evidence.
