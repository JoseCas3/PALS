# Sprint 3 — Adaptive Study Planner

## Objective

Answer "What should I study for this Exam?" with a deterministic, explainable, read-only ranking
of its assigned Topics.

## Delivered scope

- `GET /api/v1/exams/{exam_id}/study-plan`
- On-demand per-Exam Topic ranking
- Exact Decimal components and priority
- Linear 30 elapsed-day Exam urgency
- Injectable captured UTC time
- Virtual zero Mastery for unattempted Topics
- Deterministic strongest-contributor explanations
- Stable server-side ordering
- Minimal Subject-to-Exam Study Planner UI
- No planner persistence, migration, caching, or AI

## Formula and precision

```text
MasteryNeed = 1 - MasteryScore / 100
Priority = 0.50 * MasteryNeed + 0.30 * Urgency + 0.20 * ExamWeight
```

ExamWeight is the direct ExamTopic weight and is not normalized against other Topics. Python
`Decimal` constants, `ROUND_HALF_UP`, and a `0.0001` quantum are used for normalized components
and final priority. The API returns Mastery with two fixed places and planner decimals with four.
Invalid persisted Mastery or ExamTopic weight is an internal integrity failure, not clamped data.

## Urgency and time

Urgency is `clamp(1 - remaining_seconds / 2592000, 0, 1)`, where remaining time is calculated
exactly from timezone-aware UTC instants without binary floating point. It is `0.0000` at or more
than 30 days, `0.5000` at 15 days, and `1.0000` at the Exam instant. The route captures production
time exactly once through injectable `utc_now()` and passes it to the service.

An Exam earlier than the captured time returns 409 `EXAM_ALREADY_PASSED`. Historical Exams remain
valid stored data. Equality is allowed. An Exam without Topic associations returns 200 with an
empty list.

## Ranking and explanation

Items sort by priority descending, Mastery ascending, ExamTopic weight descending, and Topic UUID
ascending. Fully mastered Topics remain included. Each reason exposes the three normalized factor
values and formula weights, plus one deterministic summary naming the greatest weighted
contributor. Equal contributions prefer Mastery need, then urgency, then Exam weight.

All Topics in one Exam share the same urgency. Urgency therefore changes absolute priority but
cannot change their relative within-Exam order. Cross-Exam planning remains deferred.

## Read-only integrity

The planner first retrieves the Exam and then uses one joined ExamTopic/Topic/optional-Mastery
query. Missing Mastery becomes `Decimal("0.00")` in memory. The planner never adds, changes,
locks, flushes, commits, or deletes domain rows, and it never persists a plan or priority.

## Deferred

Global planning across Exams, AI tutoring or explanation, configurable formula rules, priority
labels, question generation, automatic grading, spaced repetition, notifications, calendar
integration, authentication, caching, workers, queues, and analytics remain out of scope.
