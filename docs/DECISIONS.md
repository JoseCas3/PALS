# Architectural Decisions

## ADR-001 Modular monolith
Accepted.

## ADR-002 PostgreSQL
Accepted.

## ADR-003 FastAPI backend
Accepted.

## ADR-004 Next.js frontend
Accepted.

## ADR-005 Provider-agnostic AI boundary
Accepted.

## ADR-006 No authentication in Alpha 0.1
Accepted.

## ADR-007 No Redis/queue initially
Accepted.

## ADR-008 No RAG in Alpha 0.1
Accepted.

## ADR-009 Evidence-based mastery
Accepted. Reading explanations does not increase mastery.

## ADR-010 Sprint 1 restrictive academic deletion
Accepted. Subjects cannot be deleted while they have Topics or Exams, and Topics cannot be
deleted while assigned to Exams. Exam deletion cascades only through ExamTopic links.

## ADR-011 ExamTopic integrity
Accepted. `(exam_id, topic_id)` is the primary key, weight is greater than 0 and no greater than
1, and the same-subject invariant is enforced in the service layer without triggers.
