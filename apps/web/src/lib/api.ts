import type { Exam, ExamTopic, Subject, Topic } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ErrorEnvelope = {
  error?: { message?: string };
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = (await response.json()) as ErrorEnvelope;
      message = payload.error?.message ?? message;
    } catch {
      // Preserve the status-based fallback when the server does not return JSON.
    }
    throw new Error(message);
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
};
