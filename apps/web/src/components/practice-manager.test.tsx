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

    await screen.findByText("Show answer reference");
    expect(screen.getByText("A value approached by a function.")).toBeInTheDocument();
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
      if (url.endsWith("/topics/topic-1/questions")) return jsonResponse([question]);
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

  it("keeps Tutor help separate from Attempt fields and hides the answer by default", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === "POST" && url.endsWith("/questions/question-1/tutor")) {
        return jsonResponse({
          interaction_id: "interaction-1",
          question_id: question.id,
          help_level: 6,
          content: "Complete solution",
          provider: "fake",
          model: "fake-model",
          prompt_version: "question_tutor.v1",
          created_at: "2026-09-12T00:00:00Z",
        });
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

    const disclosure = await screen.findByText("Show answer reference");
    const details = disclosure.closest("details");
    expect(details).not.toHaveAttribute("open");
    fireEvent.click(disclosure);
    expect(details).toHaveAttribute("open");

    fireEvent.click(screen.getByRole("radio", { name: /6\. Full solution/ }));
    fireEvent.click(screen.getByRole("button", { name: "Get help" }));
    await screen.findByText("Complete solution");
    expect(screen.getByLabelText("Hints used")).toHaveValue("0");
    expect(screen.getByLabelText("Solution seen")).not.toBeChecked();
  });

  it("generates a safe preview, prevents duplicate requests, and shows duplicate warnings", async () => {
    let resolveGeneration: ((value: object) => void) | undefined;
    const generationResponse = new Promise<object>((resolve) => {
      resolveGeneration = resolve;
    });
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === "POST" && url.endsWith("/topics/topic-1/question-generation")) {
        return generationResponse;
      }
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/topics")) return jsonResponse([topic]);
      if (url.endsWith("/topics/topic-1/questions")) return jsonResponse([question]);
      if (url.endsWith("/topics/topic-1/mastery")) {
        return jsonResponse({ topic_id: topic.id, score: "45.00", updated_at: null });
      }
      if (url.endsWith("/questions/question-1/attempts")) return jsonResponse([]);
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PracticeManager />);

    const generate = await screen.findByRole("button", { name: "Generate" });
    expect(screen.getByLabelText("Generation count")).toHaveValue("5");
    expect(screen.getByLabelText("Generation difficulty")).toHaveValue("mixed");
    fireEvent.change(screen.getByLabelText("Generation count"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Generation difficulty"), {
      target: { value: "hard" },
    });
    fireEvent.click(generate);
    fireEvent.click(screen.getByRole("button", { name: "Generating…" }));
    expect(screen.getByRole("button", { name: "Generating…" })).toBeDisabled();

    resolveGeneration?.(jsonResponse(generationResult()));
    await screen.findByText("<script>alert(1)</script>");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/topics/topic-1/question-generation",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ count: 1, difficulty: "hard" }),
      }),
    );
    const generationCalls = fetchMock.mock.calls.filter(([input, init]) =>
      init?.method === "POST" && input.toString().endsWith("/question-generation")
    );
    expect(generationCalls).toHaveLength(1);
    expect(screen.getByText("Generated answer")).toBeInTheDocument();
    expect(screen.getByText("Possible duplicate of an existing Question")).toBeInTheDocument();
    expect(screen.getByLabelText("Generated candidates").querySelector("script")).toBeNull();
    expect(screen.getByLabelText("Current mastery")).toHaveTextContent("45.00");
    expect(screen.getByLabelText("Hints used")).toHaveValue("0");
    expect(screen.queryByText(/provider selector/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/chat/i)).not.toBeInTheDocument();
  });

  it("copies one candidate into the editable existing Question form and saves normally", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === "POST" && url.endsWith("/topics/topic-1/question-generation")) {
        return jsonResponse(generationResult());
      }
      if (init?.method === "POST" && url.endsWith("/topics/topic-1/questions")) {
        const submitted = JSON.parse(String(init.body)) as typeof question;
        return jsonResponse({ ...question, ...submitted, id: "question-generated" }, 201);
      }
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/topics")) return jsonResponse([topic]);
      if (url.endsWith("/topics/topic-1/questions")) return jsonResponse([]);
      if (url.endsWith("/topics/topic-1/mastery")) {
        return jsonResponse({ topic_id: topic.id, score: "0.00", updated_at: null });
      }
      if (url.endsWith("/questions/question-generated/attempts")) return jsonResponse([]);
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PracticeManager />);

    fireEvent.click(await screen.findByRole("button", { name: "Generate" }));
    fireEvent.click(await screen.findByRole("button", { name: "Use candidate" }));
    expect(screen.getByLabelText("Question prompt")).toHaveValue("<script>alert(1)</script>");
    expect(screen.getByLabelText("Answer reference")).toHaveValue("Generated answer");
    expect(screen.getByLabelText("Question difficulty")).toHaveValue("hard");
    fireEvent.change(screen.getByLabelText("Question prompt"), {
      target: { value: "Reviewed prompt" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add question" }));
    await screen.findByText("Reviewed prompt");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/topics/topic-1/questions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          prompt: "Reviewed prompt",
          answer_reference: "Generated answer",
          difficulty: "hard",
        }),
      }),
    );
    expect(screen.queryByRole("button", { name: /save selected/i })).not.toBeInTheDocument();
  });

  it("shows generation errors, retries, and clears candidates when the Topic changes", async () => {
    const secondTopic = { ...topic, id: "topic-2", name: "Integrals" };
    let generationCalls = 0;
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === "POST" && url.endsWith("/question-generation")) {
        generationCalls += 1;
        return generationCalls === 1
          ? jsonResponse({ error: { message: "AI unavailable" } }, 503)
          : jsonResponse(generationResult());
      }
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/topics")) {
        return jsonResponse([topic, secondTopic]);
      }
      if (url.includes("/topics/") && url.endsWith("/questions")) return jsonResponse([]);
      if (url.includes("/topics/") && url.endsWith("/mastery")) {
        return jsonResponse({ topic_id: topic.id, score: "0.00", updated_at: null });
      }
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PracticeManager />);

    fireEvent.click(await screen.findByRole("button", { name: "Generate" }));
    await screen.findByText("AI unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByRole("button", { name: "Use candidate" });
    fireEvent.change(screen.getByLabelText("Practice topic"), {
      target: { value: "topic-2" },
    });
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Use candidate" })).not.toBeInTheDocument(),
    );
    expect(screen.queryByText("AI unavailable")).not.toBeInTheDocument();
  });
});

function generationResult() {
  return {
    interaction_id: "interaction-1",
    topic_id: topic.id,
    candidates: [
      {
        prompt: "<script>alert(1)</script>",
        answer_reference: "Generated answer",
        difficulty: "hard",
        duplicate_existing: true,
      },
    ],
    provider: "fake",
    model: "fake-model",
    prompt_version: "question_generation.v1",
    created_at: "2026-09-12T00:00:00Z",
  };
}

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
