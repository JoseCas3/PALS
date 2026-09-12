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
