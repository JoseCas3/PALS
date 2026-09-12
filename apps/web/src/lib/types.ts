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

export type QuestionDifficulty = "easy" | "medium" | "hard";

export type Question = {
  id: string;
  topic_id: string;
  prompt: string;
  answer_reference: string;
  difficulty: QuestionDifficulty;
  created_at: string;
  updated_at: string;
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
