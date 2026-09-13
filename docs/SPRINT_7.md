# Sprint 7 — Alpha UX and end-to-end integration

Sprint 7 connects the existing academic, planning, Practice, Mastery, Tutor, and Question Generation
capabilities into the final Alpha workflow. It does not add backend endpoints, domain models,
migrations, planner logic, or evidence semantics.

## Alpha workflow

1. Create a Subject and Topic in Academic setup.
2. Create a future Exam and assign the Topic with a weight.
3. Review the server-ranked Global Study Plan.
4. Choose **Practice this topic** on the primary recommendation or any Up next item.
5. Create or select a Question in the selected Topic.
6. Record an explicit Attempt.
7. Observe the returned Mastery and refreshed Global Study Plan while Practice remains on the Topic.

This deterministic loop works with `AI_API_KEY` blank. Tutor and Question Generation remain optional,
Question-scoped enhancements and never create Attempts or change Mastery.

## Frontend coordination

`LearningWorkspace` owns only `{ subjectId, topicId }`, `academicRevision`, and `plannerRevision`.
Children retain their lists, forms, API requests, and domain-specific state. Topic selection sets Subject
and Topic atomically. A Subject-only change clears Topic. Exam identity is never included in Practice
selection, and planner refreshes never change it.

Successful academic writes advance `academicRevision`, allowing Practice and the Exam planner to
reload their selectable academic data on the same page. Successful planner-input writes and Attempts
advance `plannerRevision`. Failed writes publish neither revision.

## Async context safety

Practice changes invalidate Questions, selected Question, Attempts, Mastery, forms, generation state,
Tutor state, loading state, errors, and success messages from the prior Topic. Topic, Question, and
context-generation guards prevent delayed reads from publishing into a newer context.

Question create, update, and delete operations finish on the server after navigation, but their results
and errors update the UI only while their initiating Topic generation remains active. A successful
Attempt always refreshes the Global Planner because it is persisted evidence; its visible Attempt,
Mastery, form, and feedback update only in the initiating Topic and Question context. Failed Attempts
never refresh the planner. Exam-specific plan responses are similarly guarded by request and Exam ID.

## Mastery and evidence

Before a Topic response exists the UI does not present a numeric Mastery. A virtual Mastery with no
`updated_at` displays `0.00 / 100` and explains that no Attempts exist. Active-context Attempt success
uses the backend response and reports the new Mastery without inventing a previous score.

Only explicit successful Attempt creation is evidence. Planner navigation, Question selection or save,
Tutor help, answer-reference viewing, and generated previews do not create evidence or refresh Mastery.

## Browser acceptance

`npm run test:e2e` starts a disposable PostgreSQL 17 database and real FastAPI container with an empty
AI key, starts the real Next.js application, and runs one Chromium happy path. The test creates the full
academic setup without reload, opens the recommendation in Practice, saves a manual Question, records
an Attempt, verifies Mastery and planner refresh, verifies Topic retention, exercises a conflict, and
checks core controls at a narrow viewport. Teardown removes the isolated Compose project and volumes.

Alpha navigation state remains in browser memory and may reset on reload. Academic data, Questions,
Attempts, and Mastery remain persisted in PostgreSQL.
