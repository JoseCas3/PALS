# PALS Product Specification

## Purpose
PALS maintains persistent academic state: subjects, topics, exams, attempts, hints used, mastery and study priorities.

PALS is not a chatbot with a database. It is a learning system that uses language models as replaceable capabilities.

## Primary user
Alpha 0.1 is single-user. Authentication, billing and multi-tenancy are out of scope.

## Core workflow
Create subject → create topic tree → create exam → associate topics → practice → evaluate attempt → update mastery → reprioritize study.

## Alpha 0.1 requirements
- Subjects CRUD
- Topics/subtopics CRUD
- Exams CRUD
- Exam-topic weights
- Tutor modes: explain, socratic, solve, review
- Question types: multiple_choice, open_answer, problem
- Attempts: answer, correctness, hints, solution_seen, time
- Mastery score 0–100
- Dashboard: upcoming exams, weakest topics, recommended next topic

## Out of scope
Authentication, billing, mobile apps, OCR, PDF/RAG, flashcards, spaced repetition, voice, podcasts, multi-user collaboration, microservices and Kubernetes.

## Success criteria
Use PALS for one real subject and obtain a useful mastery profile from real practice attempts.

## Sprint 2 evidence rules

- Questions are manually authored and use a prompt plus answer reference.
- Attempt correctness is trusted, self-reported evidence in the single-user Alpha.
- There is no AI or automatic answer grading in Sprint 2.
- Reading or editing academic content never changes mastery.
- Help scales evidence strength for both correct and incorrect Attempts; it is not a punishment.
- Attempt evidence is immutable, and a Question becomes immutable after its first Attempt.

## Sprint 3 planning rules

- A per-Exam Study Plan answers "What should I study for this Exam?"
- Priority is `0.50 * MasteryNeed + 0.30 * Urgency + 0.20 * ExamWeight`.
- Urgency increases linearly over the final 30 elapsed days before an Exam.
- Planning is deterministic, read-only, calculated on demand, and uses no AI.
- A missing Mastery row is virtual `0.00`; planning never creates it.
- Fully mastered Topics remain eligible because urgency and Exam weight still contribute.
- A past Exam remains valid history but returns a conflict when asked for a current plan.
- Within one Exam, urgency changes absolute scores but not relative Topic order because all its
  Topics share the same urgency.

## Sprint 4 Tutor surface

Sprint 4 implements question-scoped progressive help only. The six levels range from one
conceptual hint to a full solution. General Explain, Socratic, Review, Exam, Quick Review, and
multi-turn conversation modes remain future Alpha work.

Tutor activity is operational usage, not demonstrated learning. It never creates or changes an
Attempt or Mastery row and is not translated into `hints_used` or `solution_seen`.

## Sprint 5 Question generation

PALS can generate structured candidate Questions for a selected Topic. Candidates are proposals,
not learning evidence or persisted drafts. The user sees each prompt and answer reference, may copy
one into the existing editable Question form, and must explicitly submit the normal Question create
operation. Generation never creates Attempts, changes Mastery, or affects the deterministic planner.

Generation is based only on Subject/Topic metadata and model knowledge. It is not grounded in course
documents, and generated answer references may be inaccurate; human review is required.

## Sprint 6 global planning rules

- The Global Study Plan answers "What should I study now?" across all active Exams.
- An Exam is active when its date is at or after the request's single captured UTC instant; past
  Exams are silently excluded from the global queue.
- Each active ExamTopic is a separate obligation. A Topic assigned to two Exams appears twice with
  its distinct Exam context, urgency, weight, and priority.
- Global priority reuses the Sprint 3 formula exactly. There is no Exam importance or cross-Exam
  normalization in Alpha.
- The complete queue is returned in deterministic order, and its first item is the recommendation.
- Global planning is calculated on demand, read-only, unpersisted, and uses no AI.

## Sprint 7 Alpha integration

- Every Global Study Plan item can select its Subject and Topic directly in Practice.
- Subject and Topic selection is shared across the single-page workspace; Exam identity remains
  explanatory context and is not transferred into Topic-based Practice.
- Successful Attempts update visible Mastery, refresh the Global Study Plan, and never move the
  user away from the active Topic.
- Academic mutations refresh dependent selectors without requiring a browser reload.
- Navigation state is in memory. Reloading may reset selection but does not remove persisted data.
- Tutor and Question Generation remain optional and never produce learning evidence.
