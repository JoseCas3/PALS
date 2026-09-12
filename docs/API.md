# PALS API — Alpha 0.1

Base: `/api/v1`

## Subjects

- `GET /subjects` → 200
- `POST /subjects` → 201
- `GET /subjects/{id}` → 200
- `PATCH /subjects/{id}` → 200
- `DELETE /subjects/{id}` → 204, or 409 when Topics or Exams exist

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

## Deferred Alpha 0.1 endpoints

Tutor endpoints are deferred beyond Sprint 2.

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
- 409: current-state conflicts such as protected deletion, attempted-Question mutation, or
  cross-subject assignment
