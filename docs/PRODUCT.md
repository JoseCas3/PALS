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
