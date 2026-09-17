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

## ADR-012 Exact deterministic mastery

Accepted. Mastery uses Python `Decimal`, PostgreSQL `NUMERIC(5,2)`, per-Attempt
`ROUND_HALF_UP`, and fixed two-place API strings. Help scales positive and negative evidence.

## ADR-013 Atomic and concurrency-safe evidence

Accepted. `AttemptService` stages Attempt and Mastery changes and commits once. Mastery rows are
created lazily with conflict-safe insertion and locked with `SELECT ... FOR UPDATE` to prevent
lost concurrent updates.

## ADR-014 Practice evidence preservation

Accepted. Attempts are immutable. Questions become immutable after their first Attempt.
Questions, Attempts, and Mastery use restrictive foreign keys; no practice evidence is deleted
through a cascade. Topic deletion is blocked by Questions or learning evidence.

## ADR-015 Deterministic on-demand study planning

Accepted. Per-Exam Topic priority uses exact Python `Decimal` values and fixed code constants:
50% Mastery need, 30% linear urgency over a 30 elapsed-day horizon, and 20% direct ExamTopic
weight. Components and priority use four places with `ROUND_HALF_UP`. The route captures one
injectable UTC instant. Plans are read-only projections and are not persisted; missing Mastery is
virtual zero and fully mastered Topics remain included. Past Exams return
`EXAM_ALREADY_PASSED`. Reasons deterministically identify the strongest weighted contribution,
with Mastery need, urgency, then Exam weight as tie precedence. Sorting uses priority descending,
Mastery ascending, Exam weight descending, and Topic UUID ascending. Because urgency is common
within an Exam, it affects absolute scores but not within-Exam order. No AI participates.

## ADR-016 Provider-neutral Question Tutor

Accepted. Sprint 4 exposes only question-scoped help levels 1-6. TutorService depends on a neutral
AIGateway/AIProvider contract; OpenAI Responses is the first adapter, while provider and model
remain configuration. Responses are plain text, non-streaming, limited to 800 output tokens, and
use one provider attempt with a 20-second hard timeout and zero retries.

## ADR-017 Metadata-only AI observability

Accepted. Every configured Tutor call commits a pending AIInteraction before network I/O and
finalizes it afterward in a separate short transaction. Entity references use `ON DELETE SET
NULL`. No prompt, academic text, answer reference, output transcript, secret, arbitrary metadata,
or dollar-cost estimate is stored.

## ADR-018 Tutor is not evidence

Accepted. Tutor usage and AIInteraction rows cannot create or modify Attempts, Mastery,
Questions, ExamTopics, or Study Plans. Tutor levels are not mapped to `hints_used` or
`solution_seen`. Only the existing Attempt path changes Mastery.

## ADR-019 Preview-only AI Question generation

Accepted. Topic-scoped generation returns transient candidates only. Human review is mandatory,
and generation itself creates no Questions or learning evidence.

## ADR-020 Provider-native structure plus PALS validation

Accepted. A neutral JSON Schema request is mapped inside the OpenAI adapter to strict structured
output. Returned JSON remains a string across the gateway and is parsed and authoritatively
validated by PALS. Invalid candidate sets fail atomically with no automatic retry.

## ADR-021 Local textual duplicate detection

Accepted. Existing Question prompts are not sent to the provider. NFKC, trim, whitespace collapse,
and casefold detect textual matches locally. Duplicates within a generated set invalidate the set;
matches against existing Questions produce an advisory warning. Semantic detection is deferred.

## ADR-022 Existing Question persistence remains authoritative

Accepted. “Use candidate” copies one proposal into the ordinary editable Question form. The user
submits the existing one-Question POST, preserving Question validation and transaction semantics.
There is no bulk approval, candidate persistence, or Question provenance.

## ADR-023 Deterministic global on-demand planning

Accepted. The Global Study Plan reuses the Sprint 3 formula and shared exact Decimal scoring for
every ExamTopic whose Exam date is at or after one captured UTC instant. Past Exams are silently
excluded globally while the Exam-specific historical conflict remains unchanged. One joined query
loads Subject, Exam, ExamTopic, Topic, and optional Mastery inputs; sorting is authoritative in the
service and resolves ties by priority descending, Mastery ascending, Exam date ascending, exact
weight descending, Exam UUID, then Topic UUID.

Each ExamTopic remains a separate obligation, including when one Topic belongs to multiple Exams.
The complete queue is returned, with its first item serving as the recommendation. Plans are never
persisted or cached, and neither AI nor Questions participate. Exam importance and cross-Exam weight
normalization are deferred because Alpha has no supporting domain data and should require no extra
configuration.

## ADR-024 In-memory Alpha workspace coordination

Accepted. `LearningWorkspace` owns only cross-panel Practice selection and revision counters.
Children retain API and domain state. Global recommendations set Subject and Topic atomically;
Subject-only changes clear Topic, planner reranking does not navigate, and Exam identity does not
enter Practice. URL persistence and global state libraries are deferred because they add no required
Alpha capability.

Async Practice operations are context guarded. Completed writes remain valid on the server, but
old-context results and errors cannot contaminate the current Topic. Successful Attempts always
refresh the Global Planner because they are valid evidence even after navigation.

## ADR-025 Alpha hardening boundaries

Accepted. Browser operation state is scoped separately from valid server mutation completion.
Academic writes publish global revision notifications after success, while entity data, forms, and
errors are published only into their initiating Subject/Exam context. Development and E2E host
ports bind to loopback because Alpha is unauthenticated local software.

Persisted academic text rejects embedded NUL before database execution, PostgreSQL `INTEGER`
limits bound Attempt time, SQL parameters are hidden, and unexpected SQLAlchemy failures return a
generic PALS error envelope. Backend integration tests require an explicit `_test` PostgreSQL
database migrated by Alembic and never repair schema with ORM metadata.

The frontend npm lockfile remains authoritative for JavaScript dependencies. Python direct
dependencies are exactly pinned, but a transitive backend lock is deferred before Beta because
adding a new resolver workflow is beyond this focused remediation. ExamTopic request transport
continues to cross a float boundary; a decimal-safe public transport is deferred API debt, while
planner calculations over persisted values remain exact and deterministic.

## ADR-026 RAG integration recovery boundaries

Accepted. A conditional PostgreSQL update is the synchronous processing mutex; extraction and
embedding run outside transactions; complete chunks and READY profile metadata publish atomically.
If deletion wins an in-flight processing race, failure cleanup tolerates only the now-absent row and
cannot recreate it. Unexpected extant lifecycle states still fail and roll back. Attempt creation
remains the exclusive Mastery authority.

Crash-orphaned upload files, crash-stuck PROCESSING rows, and post-commit staged deletion orphans are
bounded accepted limitations until measured operations justify reconciliation tooling, workers, or
watchdogs. Exact pgvector scan, internal retrieval, transient aliases, and exact evidence lookup
remain intentional local-first boundaries.
