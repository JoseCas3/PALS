import type {
  Attempt,
  AttemptResult,
  Document,
  Exam,
  ExamTopic,
  Mastery,
  Question,
  QuestionDifficulty,
  QuestionGenerationResponse,
  GenerationDifficulty,
  GlobalStudyPlan,
  StudyPlan,
  Subject,
  Topic,
  TutorResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ErrorEnvelope = {
  error?: { code?: string; message?: string };
};

export class ApiError extends Error {
  constructor(message: string, public readonly code?: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body && !isFormData ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    let code: string | undefined;
    try {
      const payload = (await response.json()) as ErrorEnvelope;
      message = payload.error?.message ?? message;
      code = payload.error?.code;
    } catch {
      // Preserve the status-based fallback when the server does not return JSON.
    }
    throw new ApiError(message, code);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

const body = (value: object): RequestInit => ({ body: JSON.stringify(value) });

export const api = {
  listSubjects: () => request<Subject[]>("/subjects"),
  createSubject: (value: { name: string; description?: string }) =>
    request<Subject>("/subjects", { method: "POST", ...body(value) }),
  updateSubject: (id: string, value: { name: string }) =>
    request<Subject>(`/subjects/${id}`, { method: "PATCH", ...body(value) }),
  deleteSubject: (id: string) => request<void>(`/subjects/${id}`, { method: "DELETE" }),

  listDocuments: (subjectId: string) =>
    request<Document[]>(`/subjects/${subjectId}/documents`),
  uploadDocument: (subjectId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Document>(`/subjects/${subjectId}/documents`, {
      method: "POST",
      body: form,
    });
  },
  deleteDocument: (id: string) =>
    request<void>(`/documents/${id}`, { method: "DELETE" }),
  processDocument: (id: string) =>
    request<Document>(`/documents/${id}/process`, { method: "POST" }),

  listTopics: (subjectId: string) => request<Topic[]>(`/subjects/${subjectId}/topics`),
  createTopic: (subjectId: string, value: { name: string; description?: string }) =>
    request<Topic>(`/subjects/${subjectId}/topics`, { method: "POST", ...body(value) }),
  updateTopic: (id: string, value: { name: string }) =>
    request<Topic>(`/topics/${id}`, { method: "PATCH", ...body(value) }),
  deleteTopic: (id: string) => request<void>(`/topics/${id}`, { method: "DELETE" }),

  listExams: (subjectId: string) => request<Exam[]>(`/subjects/${subjectId}/exams`),
  createExam: (
    subjectId: string,
    value: { name: string; exam_date: string; description?: string },
  ) => request<Exam>(`/subjects/${subjectId}/exams`, { method: "POST", ...body(value) }),
  updateExam: (id: string, value: { name: string }) =>
    request<Exam>(`/exams/${id}`, { method: "PATCH", ...body(value) }),
  deleteExam: (id: string) => request<void>(`/exams/${id}`, { method: "DELETE" }),

  listExamTopics: (examId: string) => request<ExamTopic[]>(`/exams/${examId}/topics`),
  putExamTopic: (examId: string, topicId: string, weight: number) =>
    request<ExamTopic>(`/exams/${examId}/topics/${topicId}`, {
      method: "PUT",
      ...body({ weight }),
    }),
  deleteExamTopic: (examId: string, topicId: string) =>
    request<void>(`/exams/${examId}/topics/${topicId}`, { method: "DELETE" }),

  listQuestions: (topicId: string) => request<Question[]>(`/topics/${topicId}/questions`),
  createQuestion: (
    topicId: string,
    value: { prompt: string; answer_reference: string; difficulty: QuestionDifficulty },
  ) =>
    request<Question>(`/topics/${topicId}/questions`, { method: "POST", ...body(value) }),
  generateQuestions: (
    topicId: string,
    value: { count: number; difficulty: GenerationDifficulty },
  ) =>
    request<QuestionGenerationResponse>(`/topics/${topicId}/question-generation`, {
      method: "POST",
      ...body(value),
    }),
  updateQuestion: (
    id: string,
    value: Partial<{
      prompt: string;
      answer_reference: string;
      difficulty: QuestionDifficulty;
    }>,
  ) => request<Question>(`/questions/${id}`, { method: "PATCH", ...body(value) }),
  deleteQuestion: (id: string) =>
    request<void>(`/questions/${id}`, { method: "DELETE" }),
  listAttempts: (questionId: string) =>
    request<Attempt[]>(`/questions/${questionId}/attempts`),
  recordAttempt: (
    questionId: string,
    value: {
      correct: boolean;
      hints_used: number;
      solution_seen: boolean;
      time_spent_seconds: number;
    },
  ) =>
    request<AttemptResult>(`/questions/${questionId}/attempts`, {
      method: "POST",
      ...body(value),
    }),
  getMastery: (topicId: string) => request<Mastery>(`/topics/${topicId}/mastery`),
  getTutorHelp: (questionId: string, helpLevel: number) =>
    request<TutorResponse>(`/questions/${questionId}/tutor`, {
      method: "POST",
      ...body({ help_level: helpLevel }),
    }),
  getStudyPlan: (examId: string) => request<StudyPlan>(`/exams/${examId}/study-plan`),
  getGlobalStudyPlan: () => request<GlobalStudyPlan>("/study-plan"),
};
