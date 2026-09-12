# Sprint 2 — Practice Evidence and Mastery

## Objective

Allow PALS to answer “Am I actually learning this topic?” from demonstrated practice evidence.

## Delivered scope

- Manually authored easy, medium, and hard Questions owned by Topics
- Immutable, self-reported Attempts with help and time evidence
- One exact current Mastery score per attempted Topic
- Atomic Attempt creation and Mastery update
- PostgreSQL row locking for concurrent Attempts
- Evidence-preserving Question and Topic deletion rules
- Minimal Question, Attempt, Mastery, and recent-evidence UI

## Evidence lifecycle

Reading, creating, or updating academic content does not affect Mastery. Mastery is created lazily
inside the first successful Attempt transaction. Before that, the API reports a virtual `0.00`
score without inserting a row.

Correctness is trusted self-reported evidence in Alpha. Sprint 2 has no AI provider, automatic
grading, or generated Questions. Attempts are immutable. Once the first Attempt exists, its
Question can no longer be patched or deleted.

## Mastery calculation

Correct Attempts start at `+8`; incorrect Attempts start at `-5`. Difficulty multipliers are
`0.75`, `1.00`, and `1.25`. Zero through three hints use `1.00`, `0.80`, `0.60`, and `0.40`.
Seeing the solution overrides the hint multiplier with `0.10`.

Help represents evidence strength and intentionally reduces the magnitude of both positive and
negative changes. Each delta is quantized to `0.01` with `ROUND_HALF_UP`, added to the previous
score, and clamped to `0.00` through `100.00`. The API returns fixed-scale decimal strings.

## Transaction and concurrency

`AttemptService` locks the Question, inserts Mastery if absent, locks Mastery, calculates the
delta, stages both writes, flushes, and commits once. A failure rolls back both writes. Concurrent
requests use a stable Question-then-Mastery lock order, conflict-safe lazy insertion, and
`SELECT ... FOR UPDATE`; no update can overwrite a score it did not first lock and read.

## Deletion

- Unattempted Questions may be deleted.
- Attempted Questions return 409 for PATCH and DELETE.
- Topics with Questions return `TOPIC_HAS_QUESTIONS`.
- Topics with Attempts or Mastery return `TOPIC_HAS_LEARNING_EVIDENCE`.
- Existing ExamTopic protection remains unchanged.
- Practice foreign keys use `ON DELETE RESTRICT`; no evidence cascade exists.

## Deferred

AI, tutor/chat, automatic grading, question generation, adaptive planning, spaced repetition,
authentication, analytics, RAG, Redis, workers, and production infrastructure remain deferred.
