# Sprint 4 - AI Gateway and Question Tutor

## Objective

Add the first controlled AI capability without turning PALS into a general chatbot or weakening
evidence-based Mastery.

## Delivered scope

- `POST /api/v1/questions/{question_id}/tutor`
- Strict progressive help levels 1 through 6
- Deterministic prompt contract `question_tutor.v1`
- Provider-neutral AI request, response, provider, and gateway contracts
- One async OpenAI Responses API adapter with a configurable model
- Metadata-only AIInteraction persistence with pending/success/failure states
- Safe provider error mapping, zero retries, and a 20-second hard timeout
- Plain-text, non-streaming Tutor UI inside Question practice
- Fake/mocked provider, PostgreSQL integration, privacy, and evidence-isolation tests

## Progressive assistance

Levels 1 through 4 omit `answer_reference` entirely and provide, respectively, one concept,
principle/formula, strategy, and exactly the first concrete step. Level 5 may use the trusted
reference for correctness but gives staged guidance without the final answer. Level 6 may provide
the complete reasoning and result. Every system prompt states the requested ceiling explicitly.

## Transactions and observability

TutorService reads and validates context, builds the prompt, inserts a pending AIInteraction, and
commits. It then performs the provider call with no database transaction open. Success or neutral
failure metadata is finalized and committed afterward. Prompts and outputs are never persisted.
An interrupted process can therefore leave a meaningful pending row.

## Safety and privacy

Question and Topic text is delimited as untrusted data. This mitigates rather than solves prompt
injection. Tutor-only input limits reject oversized stored context without changing Question or
Topic CRUD rules. Output is limited to 800 tokens and 12,000 characters. The frontend renders
plain text only.

Tutor and AIInteraction activity never changes Attempts, Mastery, Questions, ExamTopics, or Study
Plans. Tutor levels are not translated into `hints_used` or `solution_seen`. Topic Tutor, general
chat, conversations, streaming, model routing, AI grading, Question generation, RAG, and cost
billing remain deferred.
