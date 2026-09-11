# PALS Database — Alpha 0.1

## subjects
id UUID PK
name varchar required
description text nullable
created_at timestamptz
updated_at timestamptz

## topics
id UUID PK
subject_id UUID FK subjects
parent_topic_id UUID nullable FK topics
name varchar required
description text nullable
importance numeric default 1.0
created_at timestamptz
updated_at timestamptz

## exams
id UUID PK
subject_id UUID FK subjects
name varchar required
exam_date timestamptz required
target_score numeric nullable
max_score numeric nullable
created_at timestamptz
updated_at timestamptz

## exam_topics
exam_id UUID FK exams
topic_id UUID FK topics
weight numeric 0..1
PK (exam_id, topic_id)

## questions
id UUID PK
topic_id UUID FK topics
type varchar
difficulty varchar
question_text text
correct_answer text
explanation text
source varchar
created_at timestamptz

## attempts
id UUID PK
question_id UUID FK questions
answer text
is_correct boolean
hints_used integer default 0
solution_seen boolean default false
attempt_number integer
response_time_seconds integer nullable
created_at timestamptz

## mastery
id UUID PK
topic_id UUID unique FK topics
score numeric 0..100
confidence numeric 0..1
last_practiced_at timestamptz nullable
total_attempts integer
correct_attempts integer
updated_at timestamptz

## study_sessions
id UUID PK
subject_id UUID FK subjects
exam_id UUID nullable FK exams
started_at timestamptz nullable
ended_at timestamptz nullable
planned_minutes integer nullable
actual_minutes integer nullable
status varchar

## ai_interactions
id UUID PK
provider varchar
model varchar
task varchar
input_tokens integer nullable
output_tokens integer nullable
latency_ms integer nullable
success boolean
error text nullable
estimated_cost numeric nullable
created_at timestamptz

## Integrity rules
- mastery.score stays 0..100
- exam_topics.weight stays 0..1
- child topic belongs to same subject as parent
- exam topic belongs to same subject as exam
- attempt creation + mastery update should be transactional
