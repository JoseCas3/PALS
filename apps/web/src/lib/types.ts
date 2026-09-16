export type Subject = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type Topic = {
  id: string;
  subject_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type Exam = {
  id: string;
  subject_id: string;
  name: string;
  exam_date: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type ExamTopic = {
  exam_id: string;
  topic_id: string;
  weight: number;
};

export type DocumentStatus = "UPLOADED" | "PROCESSING" | "READY" | "FAILED";

export type Document = {
  id: string;
  subject_id: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  checksum_sha256: string;
  status: DocumentStatus;
  error_code: string | null;
  processing_version: number;
  embedding_provider: string | null;
  embedding_model: string | null;
  embedding_dimensions: number | null;
  created_at: string;
  updated_at: string;
};

export type QuestionDifficulty = "easy" | "medium" | "hard";
export type GenerationDifficulty = QuestionDifficulty | "mixed";

export type Question = {
  id: string;
  topic_id: string;
  prompt: string;
  answer_reference: string;
  difficulty: QuestionDifficulty;
  created_at: string;
  updated_at: string;
};

export type QuestionGenerationCandidate = {
  prompt: string;
  answer_reference: string;
  difficulty: QuestionDifficulty;
  duplicate_existing: boolean;
};

export type QuestionGenerationResponse = {
  interaction_id: string;
  topic_id: string;
  candidates: QuestionGenerationCandidate[];
  provider: string;
  model: string;
  prompt_version: string;
  created_at: string;
};

export type Attempt = {
  id: string;
  question_id: string;
  correct: boolean;
  hints_used: number;
  solution_seen: boolean;
  time_spent_seconds: number;
  created_at: string;
};

export type Mastery = {
  topic_id: string;
  score: string;
  updated_at: string | null;
};

export type AttemptResult = {
  attempt: Attempt;
  mastery: Mastery;
};

export type TutorResponse = {
  interaction_id: string | null;
  question_id: string;
  help_level: number;
  grounding_mode: "NONE" | "REQUIRED";
  outcome: "ANSWER" | "INSUFFICIENT_EVIDENCE";
  content: string | null;
  answer: string | null;
  citations: GroundedCitation[];
  provider: string | null;
  model: string | null;
  prompt_version: string;
  created_at: string | null;
};

export type GroundedCitation = {
  alias: string;
  chunk_id: string;
  document_id: string;
  document_filename: string;
  page_start: number;
  page_end: number;
};

export type PlannerFactorCode = "mastery_need" | "urgency" | "exam_weight";

export type PlannerReasonFactor = {
  code: PlannerFactorCode;
  value: string;
  formula_weight: string;
};

export type PlannerReason = {
  summary: string;
  factors: PlannerReasonFactor[];
};

export type StudyPlanItem = {
  topic_id: string;
  topic_name: string;
  mastery_score: string;
  mastery_need: string;
  urgency: string;
  exam_weight: string;
  priority: string;
  reason: PlannerReason;
};

export type StudyPlan = {
  exam_id: string;
  exam_name: string;
  exam_date: string;
  generated_at: string;
  items: StudyPlanItem[];
};

export type GlobalStudyPlanItem = StudyPlanItem & {
  subject_id: string;
  subject_name: string;
  exam_id: string;
  exam_name: string;
  exam_date: string;
};

export type GlobalStudyPlan = {
  generated_at: string;
  items: GlobalStudyPlanItem[];
};
