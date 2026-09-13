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

## ADR-015 Deterministic on-demand study planning

Accepted. Per-Exam Topic priority uses exact Python `Decimal` values and fixed code constants:
50% Mastery need, 30% linear urgency over a 30 elapsed-day horizon, and 20% direct ExamTopic
weight. Components and priority use four places with `ROUND_HALF_UP`. The route captures one
injectable UTC instant. Plans are read-only projections and are not persisted; missing Mastery is
virtual zero and fully mastered Topics remain included. Past Exams return
`EXAM_ALREADY_PASSED`. Reasons deterministically identify the strongest weighted contribution,
with Mastery need, urgency, then Exam weight as tie precedence. Sorting uses priority descending,
Mastery ascending, Exam weight descending, and Topic UUID ascending. Because urgency is common
within an Exam, it affects absolute scores but not within-Exam order. No AI participates.

## ADR-016 Provider-neutral Question Tutor

Accepted. Sprint 4 exposes only question-scoped help levels 1-6. TutorService depends on a neutral
AIGateway/AIProvider contract; OpenAI Responses is the first adapter, while provider and model
remain configuration. Responses are plain text, non-streaming, limited to 800 output tokens, and
use one provider attempt with a 20-second hard timeout and zero retries.

## ADR-017 Metadata-only AI observability

Accepted. Every configured Tutor call commits a pending AIInteraction before network I/O and
finalizes it afterward in a separate short transaction. Entity references use `ON DELETE SET
NULL`. No prompt, academic text, answer reference, output transcript, secret, arbitrary metadata,
or dollar-cost estimate is stored.

## ADR-018 Tutor is not evidence

Accepted. Tutor usage and AIInteraction rows cannot create or modify Attempts, Mastery,
Questions, ExamTopics, or Study Plans. Tutor levels are not mapped to `hints_used` or
`solution_seen`. Only the existing Attempt path changes Mastery.
