# PALS API — Alpha 0.1

Base: `/api/v1`

Sprint 7 adds no endpoint or backend contract. The Alpha workspace composes these existing APIs in the
frontend; Practice selection and refresh revisions are in-memory UI concerns and are never persisted.

## Subjects

- `GET /subjects` → 200
- `POST /subjects` → 201
- `GET /subjects/{id}` → 200
- `PATCH /subjects/{id}` → 200
- `DELETE /subjects/{id}` → 204, or 409 when Topics or Exams exist

## Documents

- `POST /subjects/{subject_id}/documents` returns 201 and accepts multipart field `file`.
- `GET /subjects/{subject_id}/documents` returns 200 with an oldest-first Subject-scoped list.
- `GET /documents/{document_id}` returns 200 with public metadata.
- `DELETE /documents/{document_id}` returns 204 after deleting the file and row.
- `POST /documents/{document_id}/process` processes an `UPLOADED`, `FAILED`, or legacy R2 READY
  PDF and returns 200 only after atomically publishing all persistent chunks and embeddings.

R1 accepts PDF files only. It validates extension, supplied MIME type, configured size limit, and
the `%PDF-` signature before storing bytes under an opaque key. Responses never expose the storage
key or filesystem path. Duplicate content within one Subject returns 409
`DOCUMENT_ALREADY_EXISTS`; the same content in a different Subject is allowed. Valid Subject
deletion also cleans associated Document files and cascades their metadata rows.

Document errors use `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`, `INVALID_PDF`,
`DOCUMENT_ALREADY_EXISTS`, `DOCUMENT_NOT_FOUND`, and `DOCUMENT_STORAGE_ERROR` as applicable.

Processing may return `TEXT_EXTRACTION_FAILED`, `TEXT_EXTRACTION_INSUFFICIENT`, `CHUNKING_FAILED`,
`EMBEDDING_UNAVAILABLE`, `EMBEDDING_FAILED`, `EMBEDDING_DIMENSION_MISMATCH`, or
`PROCESSING_FAILED`. PROCESSING and fully R3 READY documents reject processing with
`DOCUMENT_ALREADY_PROCESSING` and `DOCUMENT_ALREADY_PROCESSED`. A legacy R2 READY document is
eligible only when all embedding metadata is null and no chunks exist. Chunk text, IDs, and vectors
are never exposed by the public API.

## Topics

- `GET /subjects/{id}/topics` → 200
- `POST /subjects/{id}/topics` → 201
- `GET /topics/{id}` → 200
- `PATCH /topics/{id}` → 200
- `DELETE /topics/{id}` → 204, or 409 when assigned to an Exam

Topic Subject ownership is determined by the nested create route and is immutable.

## Exams

- `GET /subjects/{id}/exams` → 200
- `POST /subjects/{id}/exams` → 201
- `GET /exams/{id}` → 200
- `PATCH /exams/{id}` → 200
- `DELETE /exams/{id}` → 204

Exam Subject ownership is determined by the nested create route and is immutable. Exam dates
must include a timezone, are normalized to UTC, and may be historical.

## Exam Topics

- `GET /exams/{exam_id}/topics` → 200
- `PUT /exams/{exam_id}/topics/{topic_id}` → 200 for create and update
- `DELETE /exams/{exam_id}/topics/{topic_id}` → 204

PUT body:

```json
{"weight": 0.5}
```

Weight must satisfy `0 < weight <= 1`. Duplicate pairs are prevented, and Exam and Topic must
belong to the same Subject. No total-weight constraint is imposed in Sprint 1.

## Questions

- `GET /topics/{topic_id}/questions` → 200, deterministic oldest-first list
- `POST /topics/{topic_id}/questions` → 201
- `GET /questions/{question_id}` → 200
- `PATCH /questions/{question_id}` → 200, or 409 after an Attempt exists
- `DELETE /questions/{question_id}` → 204, or 409 `QUESTION_HAS_ATTEMPTS`

Question create fields are `prompt`, `answer_reference`, and optional `difficulty` (`easy`,
`medium`, or `hard`, default `medium`). Topic ownership cannot be changed.

## Attempts

- `POST /questions/{question_id}/attempts` → 201
- `GET /questions/{question_id}/attempts` → 200, deterministic newest-first list

Attempt creation requires `correct`, `hints_used`, `solution_seen`, and `time_spent_seconds`.
Correctness is trusted self-reported Alpha evidence. Attempts cannot be updated or deleted.
Creation returns both the committed Attempt and resulting Mastery.

## Mastery

- `GET /topics/{topic_id}/mastery` → 200

Scores are fixed two-place decimal strings. Before the first Attempt the endpoint returns
`{"topic_id":"...","score":"0.00","updated_at":null}` without creating a database row.
There is no mastery mutation endpoint.

## Study Plan

- `GET /exams/{exam_id}/study-plan` -> 200

The response contains Exam metadata, the captured UTC `generated_at`, and Topics ordered by
priority descending, Mastery ascending, ExamTopic weight descending, then Topic UUID ascending.
Mastery remains a fixed two-place string. Mastery need, urgency, Exam weight, priority, reason
factor values, and formula weights are fixed four-place strings.

Priority is `0.50 * MasteryNeed + 0.30 * Urgency + 0.20 * ExamWeight`, calculated with Python
`Decimal` and `ROUND_HALF_UP`. Urgency is linear over 30 elapsed days, from `0.0000` at or beyond
30 days to `1.0000` at the Exam instant. Every Topic in one Exam shares urgency, so it changes
absolute scores but not within-Exam order.

The deterministic reason reports the strongest weighted contributor. Equal contributions prefer
Mastery need, then urgency, then Exam weight. A missing Mastery row is virtual `0.00`; a fully
mastered Topic remains included. An Exam without Topics returns an empty `items` list. Past Exams
return 409 `EXAM_ALREADY_PASSED`. Responses include `Cache-Control: no-store`. Planning performs
no writes and uses no AI.

## Global Study Plan

- `GET /study-plan` -> 200

The endpoint accepts no parameters or body. Its envelope contains one captured UTC `generated_at`
and the complete globally ordered `items` array. Each item contains Subject, Exam, and Topic IDs
and names, Exam date, Mastery, normalized planner components, priority, and the existing
deterministic reason. Mastery is a fixed two-place string and planner decimals are fixed four-place
strings. `items[0]` is the primary recommendation; there is no separate recommendation field.

An Exam is active when `exam_date >= generated_at`. Past Exams are silently excluded, exact-time
Exams are included with urgency `1.0000`, active Exams without assigned Topics contribute nothing,
and fully mastered Topics remain eligible. The same Topic assigned to multiple Exams produces one
item per ExamTopic.

Global ordering is priority descending, Mastery ascending, Exam date ascending, exact persisted
ExamTopic weight descending, Exam UUID ascending, then Topic UUID ascending. The server is the sole
ranking authority. Empty academic or active-workload states return 200 with an empty `items` array.
Responses include `Cache-Control: no-store`. The projection performs one SELECT, no writes, and no
AI calls.

## Question Generation

- `POST /topics/{topic_id}/question-generation` -> 200

Request fields are strict `count` (default 5, minimum 1, maximum 10) and `difficulty` (default
`mixed`, or `easy`, `medium`, `hard`). Extra fields are rejected. A specific difficulty requires
every candidate to match; mixed allows any valid difficulty.

The response contains interaction and Topic IDs, provider/model metadata, prompt version
`question_generation.v1`, creation time, and exactly the requested number of candidates. Each
candidate contains trimmed `prompt` (maximum 1,000 characters), required `answer_reference`
(maximum 2,000), difficulty, and a locally calculated `duplicate_existing` flag. Responses include
`Cache-Control: no-store`.

Malformed, empty, incomplete, refused, or otherwise unusable provider output returns 502
`AI_PROVIDER_INVALID_RESPONSE`. Decoded JSON that violates the candidate contract, count,
difficulty, or within-response uniqueness returns 422 `GENERATED_CANDIDATES_INVALID`. Oversized
Topic context returns 422 `GENERATION_CONTEXT_TOO_LARGE`; neutral provider errors retain the Tutor
502/503/504 mappings.

Candidates are previews only. To approve one, the frontend copies it into the existing Question
form and uses `POST /topics/{topic_id}/questions`. Normalized duplicates against existing Questions
are advisory and do not block that endpoint.

## Deferred Alpha 0.1 endpoints

Topic Tutor, conversations, general chat, AI grading, bulk approval, and generation history remain
deferred.

## Question Tutor

- `POST /questions/{question_id}/tutor` -> 200

The request requires a strict integer `help_level` from 1 through 6 and accepts optional
`grounding_mode` (`NONE`, the default, or `REQUIRED`). Subject context is derived from the Question;
clients do not supply a Subject ID. Responses use `Cache-Control: no-store` and include typed
`grounding_mode`, `outcome`, `answer`, and `citations` alongside compatible `content`.

Levels provide, in order: conceptual hint, principle/formula, strategy, first concrete step,
guided solution without the final answer, and full solution. Levels 1 through 4 never send the
Question answer reference to the provider. Levels 5 and 6 include it in a separate trusted-data
block; level 5 still withholds the final answer.

Oversized Tutor context returns 422 `TUTOR_CONTEXT_TOO_LARGE`. Provider errors map to 502 or 503;
timeouts return 504. Safe provider errors may include the interaction ID in `details`. Missing AI
configuration returns 503 `AI_PROVIDER_UNAVAILABLE` without affecting other endpoints.

REQUIRED mode calls internal Subject-scoped retrieval before generation. Insufficient evidence
returns 200 with `outcome=INSUFFICIENT_EVIDENCE`, null answer/content and interaction/provider
metadata, and empty citations; there is no generative call. A grounded `ANSWER` contains at least
one server-validated citation with alias, chunk ID, Document ID, original filename, and integer page
range. Malformed structured output, no citations, or any fabricated alias returns sanitized 502
`GROUNDING_INVALID_RESPONSE`. Provider failures retain their existing codes.

## Health

- `GET /health`
- `GET /ready`

Health routes are intentionally outside `/api/v1`.

## Errors

All Sprint 1 errors, including request validation errors, use:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Topic not found",
    "details": null
  }
}
```

- 422: malformed IDs/dates, blank names, invalid weights, or invalid request bodies
- 404: missing requested or referenced resources
- 409: current-state conflicts such as protected deletion, attempted-Question mutation,
  cross-subject assignment, or requesting a Study Plan for a past Exam
