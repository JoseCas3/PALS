# PALS API — Alpha 0.1

Base: /api/v1

## Subjects
GET /subjects
POST /subjects
GET /subjects/{id}
PATCH /subjects/{id}
DELETE /subjects/{id}

## Topics
GET /subjects/{id}/topics
POST /subjects/{id}/topics
GET /topics/{id}
PATCH /topics/{id}
DELETE /topics/{id}

## Exams
GET /exams
POST /exams
GET /exams/{id}
PATCH /exams/{id}
DELETE /exams/{id}
PUT /exams/{exam_id}/topics/{topic_id}

## Questions
POST /questions/generate
GET /topics/{topic_id}/questions
GET /questions/{id}

## Attempts
POST /questions/{id}/attempts

## Mastery
GET /topics/{id}/mastery

## Tutor
POST /tutor/message

Modes: explain, socratic, solve, review

## Health
GET /health
GET /ready

## Error shape
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Topic not found",
    "details": null
  }
}
