# Sprint 6 — Global Adaptive Planner

## Objective

Answer "Across everything I currently need to study, what should I study now?" with one
deterministic queue across active Exams, Subjects, and ExamTopics.

## Delivered scope

- `GET /api/v1/study-plan`
- One captured, injectable UTC instant per request
- One joined read projection across active academic obligations
- Exact reuse of the Sprint 3 Decimal scoring and deterministic reasons
- Stable cross-Exam ordering with complete tie resolution
- One item per ExamTopic, including the same Topic in multiple Exams
- Virtual zero Mastery without lazy persistence
- A compact frontend recommendation and ordered "Up next" list
- Explicit refresh after planner-input mutations and stale-response suppression
- No persistence, migration, caching, AI dependency, or planner configuration

## Active workload

An Exam is active exactly when `exam_date >= generated_at`. Future and exact-time Exams are
included; past Exams are silently excluded. Active Exams without ExamTopics contribute no rows.
Unassigned Topics do not appear. Fully mastered Topics remain eligible because urgency and weight
can still contribute priority.

The Exam-specific endpoint remains different by design: explicitly requesting a past Exam still
returns `409 EXAM_ALREADY_PASSED`.

## Scoring and ordering

Global and Exam-specific planning call the same pure scoring operation:

```text
MasteryNeed = 1 - MasteryScore / 100
Priority = 0.50 * MasteryNeed + 0.30 * Urgency + 0.20 * ExamWeight
Urgency = clamp(1 - remaining_seconds / 2592000, 0, 1)
```

Calculations use Python `Decimal`, a `0.0001` quantum, and `ROUND_HALF_UP`. Global items sort by
priority descending, Mastery ascending, Exam date ascending, exact persisted ExamTopic weight
descending, Exam UUID ascending, then Topic UUID ascending. Database order and names do not affect
the result.

## Read and evidence integrity

The repository executes one SELECT joining Exam, Subject, ExamTopic, Topic, and optional Mastery.
Missing Mastery is `0.00` in memory only. Planning performs no inserts, updates, deletes, row locks,
flushes, or commits and never reads Questions or AIInteraction. Only successful explicit Attempt
creation changes Mastery.

## Frontend behavior

The first returned item is displayed as "Study this now" and the remaining server-ordered rows as
"Up next." Subject and Exam context distinguish repeated Topics. The plan loads initially and
refreshes manually or after successful Attempt, Exam, ExamTopic, and relevant rename mutations.
Question and Tutor operations do not refresh it. Request generations prevent stale results from
overwriting newer plans.

## Deferred

Exam importance, configurable coefficients, weight normalization, planner history, study-session
scheduling, available-time modeling, spaced repetition, calendar integration, notifications,
analytics, AI ranking, RAG, authentication, background jobs, and cross-panel navigation remain out
of scope.
