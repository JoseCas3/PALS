import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PracticeManager } from "./practice-manager";

const subject = entity("subject-1", "Calculus");
const topic = { ...entity("topic-1", "Limits"), subject_id: subject.id };
const question = {
  id: "question-1",
  topic_id: topic.id,
  prompt: "What is a limit?",
  answer_reference: "A value approached by a function.",
  difficulty: "medium",
  created_at: "2026-09-11T00:00:00Z",
  updated_at: "2026-09-11T00:00:00Z",
};

describe("PracticeManager", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("records evidence, prevents duplicate submission, and uses backend mastery", async () => {
    let resolveAttempt: ((value: object) => void) | undefined;
    const attemptResponse = new Promise<object>((resolve) => {
      resolveAttempt = resolve;
    });
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === "POST" && url.endsWith("/questions/question-1/attempts")) {
        return attemptResponse;
      }
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/topics")) return jsonResponse([topic]);
      if (url.endsWith("/topics/topic-1/questions")) return jsonResponse([question]);
      if (url.endsWith("/topics/topic-1/mastery")) {
        return jsonResponse({ topic_id: topic.id, score: "0.00", updated_at: null });
      }
      if (url.endsWith("/questions/question-1/attempts")) return jsonResponse([]);
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PracticeManager />);

    await screen.findByText("Answer reference: A value approached by a function.");
    fireEvent.change(screen.getByLabelText("Hints used"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Time spent seconds"), {
      target: { value: "45" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Record attempt" }));
    expect(screen.getByRole("button", { name: "Recording…" })).toBeDisabled();

    resolveAttempt?.(
      jsonResponse({
        attempt: {
          id: "attempt-1",
          question_id: question.id,
          correct: true,
          hints_used: 1,
          solution_seen: false,
          time_spent_seconds: 45,
          created_at: "2026-09-11T01:00:00Z",
        },
        mastery: {
          topic_id: topic.id,
          score: "91.23",
          updated_at: "2026-09-11T01:00:00Z",
        },
      }),
    );

    await waitFor(() => expect(screen.getByLabelText("Current mastery")).toHaveTextContent("91.23"));
    expect(screen.getByText("1 hints · solution hidden · 45s")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/questions/question-1/attempts",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("creates a manual question", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === "POST" && url.endsWith("/topics/topic-1/questions")) {
        return jsonResponse({ ...question, id: "question-2", prompt: "New prompt" }, 201);
      }
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/topics")) return jsonResponse([topic]);
      if (url.endsWith("/topics/topic-1/questions")) return jsonResponse([]);
      if (url.endsWith("/topics/topic-1/mastery")) {
        return jsonResponse({ topic_id: topic.id, score: "0.00", updated_at: null });
      }
      if (url.endsWith("/questions/question-2/attempts")) return jsonResponse([]);
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PracticeManager />);

    const promptInput = await screen.findByLabelText("Question prompt");
    fireEvent.change(promptInput, {
      target: { value: "New prompt" },
    });
    fireEvent.change(screen.getByLabelText("Answer reference"), {
      target: { value: "New answer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add question" }));
    await screen.findByText("New prompt");
  });
});

function jsonResponse(payload: object, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  };
}

function entity(id: string, name: string) {
  return {
    id,
    name,
    description: null,
    created_at: "2026-09-11T00:00:00Z",
    updated_at: "2026-09-11T00:00:00Z",
  };
}
