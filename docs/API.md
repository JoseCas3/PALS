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

## Deferred Alpha 0.1 endpoints

Questions, Attempts, Mastery, and Tutor endpoints are deferred beyond Sprint 1.

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
- 409: current-state conflicts such as protected deletion or cross-subject assignment
