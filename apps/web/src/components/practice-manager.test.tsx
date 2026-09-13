import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
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
    const onPlannerInputsChanged = vi.fn();
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
    renderPractice({ onAttemptRecorded: onPlannerInputsChanged });

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
    expect(onPlannerInputsChanged).toHaveBeenCalledTimes(1);
  });

  it("does not refresh the planner or change Mastery when an Attempt fails", async () => {
    const onAttemptRecorded = vi.fn();
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === "POST" && url.endsWith("/questions/question-1/attempts")) {
        return jsonResponse({ error: { message: "Attempt rejected" } }, 409);
      }
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/topics")) return jsonResponse([topic]);
      if (url.endsWith("/topics/topic-1/questions")) return jsonResponse([question]);
      if (url.endsWith("/topics/topic-1/mastery")) {
        return jsonResponse({ topic_id: topic.id, score: "40.00", updated_at: "2026-09-11T00:00:00Z" });
      }
      if (url.endsWith("/questions/question-1/attempts")) return jsonResponse([]);
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPractice({ onAttemptRecorded });

    await screen.findByText("Show answer reference");
    fireEvent.click(screen.getByRole("button", { name: "Record attempt" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Attempt rejected");
    expect(screen.getByLabelText("Current mastery")).toHaveTextContent("40.00");
    expect(onAttemptRecorded).not.toHaveBeenCalled();
    expect(screen.queryByText(/Attempt recorded/)).not.toBeInTheDocument();
  });

  it("creates a manual question", async () => {
    const onPlannerInputsChanged = vi.fn();
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
    renderPractice({ onAttemptRecorded: onPlannerInputsChanged });

    const promptInput = await screen.findByLabelText("Question prompt");
    fireEvent.change(promptInput, {
      target: { value: "New prompt" },
    });
    fireEvent.change(screen.getByLabelText("Answer reference"), {
      target: { value: "New answer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add question" }));
    await screen.findByText("New prompt");
    expect(onPlannerInputsChanged).not.toHaveBeenCalled();
  });

  it("keeps Tutor help separate from Attempt fields and hides the answer by default", async () => {
    const onPlannerInputsChanged = vi.fn();
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
    renderPractice({ onAttemptRecorded: onPlannerInputsChanged });

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
    expect(onPlannerInputsChanged).not.toHaveBeenCalled();
  });

  it("generates a safe preview, prevents duplicate requests, and shows duplicate warnings", async () => {
    const onPlannerInputsChanged = vi.fn();
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
    renderPractice({ onAttemptRecorded: onPlannerInputsChanged });

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
    expect(onPlannerInputsChanged).not.toHaveBeenCalled();
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
    renderPractice();

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
    renderPractice();

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

  it("clears all old Topic context when an external Topic selection arrives", async () => {
    const secondTopic = { ...topic, id: "topic-2", name: "Integrals" };
    const oldAttempt = {
      id: "attempt-1",
      question_id: question.id,
      correct: true,
      hints_used: 1,
      solution_seen: false,
      time_spent_seconds: 12,
      created_at: "2026-09-12T00:00:00Z",
    };
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === "POST" && url.endsWith("/question-generation")) {
        return jsonResponse(generationResult());
      }
      if (init?.method === "POST" && url.endsWith("/questions/question-1/tutor")) {
        return jsonResponse({
          interaction_id: "interaction-1",
          question_id: question.id,
          help_level: 1,
          content: "Old tutor guidance",
          provider: "fake",
          model: "fake-model",
          prompt_version: "question_tutor.v1",
          created_at: "2026-09-12T00:00:00Z",
        });
      }
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/topics")) return jsonResponse([topic, secondTopic]);
      if (url.endsWith("/topics/topic-1/questions")) return jsonResponse([question]);
      if (url.endsWith("/topics/topic-2/questions")) return jsonResponse([]);
      if (url.endsWith("/topics/topic-1/mastery")) {
        return jsonResponse({ topic_id: topic.id, score: "45.00", updated_at: "2026-09-12T00:00:00Z" });
      }
      if (url.endsWith("/topics/topic-2/mastery")) {
        return jsonResponse({ topic_id: secondTopic.id, score: "0.00", updated_at: null });
      }
      if (url.endsWith("/questions/question-1/attempts")) return jsonResponse([oldAttempt]);
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPractice();

    await screen.findByText(/1 hints.*solution hidden.*12s/);
    fireEvent.change(screen.getByLabelText("Question prompt"), { target: { value: "Old draft" } });
    fireEvent.change(screen.getByLabelText("Time spent seconds"), { target: { value: "99" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));
    await screen.findByRole("button", { name: "Use candidate" });
    fireEvent.click(screen.getByRole("button", { name: "Get help" }));
    await screen.findByText("Old tutor guidance");

    fireEvent.change(screen.getByLabelText("Practice topic"), { target: { value: secondTopic.id } });

    await screen.findByText("Calculus / Integrals");
    await screen.findByText("Create a Question manually, or generate an optional AI preview.");
    expect(screen.getByLabelText("Question prompt")).toHaveValue("");
    expect(screen.getByLabelText("Current mastery")).toHaveTextContent("0.00");
    expect(screen.queryByText("What is a limit?")).not.toBeInTheDocument();
    expect(screen.queryByText("Old tutor guidance")).not.toBeInTheDocument();
    expect(screen.queryByText(/1 hints.*solution hidden.*12s/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Use candidate" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Time spent seconds")).not.toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("refreshes selectable academic data after a successful same-page mutation", async () => {
    const secondTopic = { ...topic, id: "topic-2", name: "Integrals" };
    let topicLoads = 0;
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/topics")) {
        topicLoads += 1;
        return jsonResponse(topicLoads === 1 ? [topic] : [topic, secondTopic]);
      }
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    function RevisionHarness() {
      const [academicRevision, setAcademicRevision] = useState(0);
      return <>
        <button type="button" onClick={() => setAcademicRevision((value) => value + 1)}>
          Publish academic revision
        </button>
        <PracticeManager
          selectedSubjectId={subject.id}
          selectedTopicId=""
          academicRevision={academicRevision}
          onSubjectSelected={vi.fn()}
          onTopicSelected={vi.fn()}
        />
      </>;
    }

    render(<RevisionHarness />);
    await waitFor(() => expect(screen.getByLabelText("Practice topic")).toBeEnabled());
    expect(screen.queryByRole("option", { name: "Integrals" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Publish academic revision" }));
    expect(await screen.findByRole("option", { name: "Integrals" })).toBeInTheDocument();
    expect(topicLoads).toBe(2);
  });

  it.each(["success", "failure"] as const)(
    "ignores stale Question and Mastery read %s after a Topic change",
    async (outcome) => {
    const secondTopic = { ...topic, id: "topic-2", name: "Integrals" };
    const secondQuestion = { ...question, id: "question-2", topic_id: secondTopic.id, prompt: "Integrate x" };
    let resolveOldQuestions: ((value: object) => void) | undefined;
    const oldQuestions = new Promise<object>((resolve) => { resolveOldQuestions = resolve; });
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/topics")) return jsonResponse([topic, secondTopic]);
      if (url.endsWith("/topics/topic-1/questions")) return oldQuestions;
      if (url.endsWith("/topics/topic-1/mastery")) return jsonResponse({ topic_id: topic.id, score: "10.00", updated_at: null });
      if (url.endsWith("/topics/topic-2/questions")) return jsonResponse([secondQuestion]);
      if (url.endsWith("/topics/topic-2/mastery")) return jsonResponse({ topic_id: secondTopic.id, score: "60.00", updated_at: "2026-09-12T00:00:00Z" });
      if (url.endsWith("/questions/question-2/attempts")) return jsonResponse([]);
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPractice();

    await waitFor(() => expect(screen.getByLabelText("Practice topic")).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Practice topic"), { target: { value: secondTopic.id } });
    expect(await screen.findAllByText("Integrate x")).toHaveLength(2);
    expect(screen.getByLabelText("Current mastery")).toHaveTextContent("60.00");

    resolveOldQuestions?.(outcome === "success"
      ? jsonResponse([question])
      : jsonResponse({ error: { message: "Stale failure" } }, 500));
    await waitFor(() => expect(screen.queryByText("Stale failure")).not.toBeInTheDocument());
    expect(screen.queryByText("What is a limit?")).not.toBeInTheDocument();
    expect(screen.getAllByText("Integrate x")).toHaveLength(2);
    },
  );

  it.each(["success", "failure"] as const)(
    "ignores a stale Attempt read %s after a Topic change",
    async (outcome) => {
      const secondTopic = { ...topic, id: "topic-2", name: "Integrals" };
      const secondQuestion = { ...question, id: "question-2", topic_id: secondTopic.id, prompt: "Integrate x" };
      let resolveOldAttempts: ((value: object) => void) | undefined;
      const oldAttempts = new Promise<object>((resolve) => { resolveOldAttempts = resolve; });
      const fetchMock = vi.fn(async (input: string | URL | Request) => {
        const url = input.toString();
        if (url.endsWith("/subjects")) return jsonResponse([subject]);
        if (url.endsWith("/subjects/subject-1/topics")) return jsonResponse([topic, secondTopic]);
        if (url.endsWith("/topics/topic-1/questions")) return jsonResponse([question]);
        if (url.endsWith("/topics/topic-2/questions")) return jsonResponse([secondQuestion]);
        if (url.endsWith("/topics/topic-1/mastery")) return jsonResponse({ topic_id: topic.id, score: "10.00", updated_at: null });
        if (url.endsWith("/topics/topic-2/mastery")) return jsonResponse({ topic_id: secondTopic.id, score: "60.00", updated_at: "2026-09-12T00:00:00Z" });
        if (url.endsWith("/questions/question-1/attempts")) return oldAttempts;
        if (url.endsWith("/questions/question-2/attempts")) return jsonResponse([]);
        return jsonResponse({ error: { message: "Unexpected request" } }, 500);
      });
      vi.stubGlobal("fetch", fetchMock);
      renderPractice();

      await screen.findByText("Show answer reference");
      fireEvent.change(screen.getByLabelText("Practice topic"), { target: { value: secondTopic.id } });
      expect(await screen.findAllByText("Integrate x")).toHaveLength(2);

      resolveOldAttempts?.(outcome === "success"
        ? jsonResponse([{
          id: "stale-attempt",
          question_id: question.id,
          correct: true,
          hints_used: 3,
          solution_seen: true,
          time_spent_seconds: 999,
          created_at: "2026-09-12T00:00:00Z",
        }])
        : jsonResponse({ error: { message: "Stale attempts failed" } }, 500));

      await waitFor(() => expect(screen.queryByText("999s")).not.toBeInTheDocument());
      expect(screen.queryByText("Stale attempts failed")).not.toBeInTheDocument();
      expect(screen.getByLabelText("Current mastery")).toHaveTextContent("60.00");
    },
  );

  it("does not let a delayed old-Topic Question create overwrite the new Topic", async () => {
    const secondTopic = { ...topic, id: "topic-2", name: "Integrals" };
    let resolveCreate: ((value: object) => void) | undefined;
    const pendingCreate = new Promise<object>((resolve) => { resolveCreate = resolve; });
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === "POST" && url.endsWith("/topics/topic-1/questions")) return pendingCreate;
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/topics")) return jsonResponse([topic, secondTopic]);
      if (url.includes("/topics/") && url.endsWith("/questions")) return jsonResponse([]);
      if (url.includes("/topics/") && url.endsWith("/mastery")) return jsonResponse({ topic_id: url.includes("topic-2") ? secondTopic.id : topic.id, score: "0.00", updated_at: null });
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPractice();

    await screen.findByText("Create a Question manually, or generate an optional AI preview.");
    fireEvent.change(screen.getByLabelText("Question prompt"), { target: { value: "Old Topic Question" } });
    fireEvent.change(screen.getByLabelText("Answer reference"), { target: { value: "Old answer" } });
    fireEvent.click(screen.getByRole("button", { name: "Add question" }));
    fireEvent.change(screen.getByLabelText("Practice topic"), { target: { value: secondTopic.id } });
    await waitFor(() => expect(screen.getByText("Calculus / Integrals")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Question prompt"), { target: { value: "New Topic Draft" } });

    resolveCreate?.(jsonResponse({ ...question, id: "old-created", prompt: "Old Topic Question" }, 201));
    await waitFor(() => expect(screen.queryByText("Old Topic Question")).not.toBeInTheDocument());
    expect(screen.getByLabelText("Question prompt")).toHaveValue("New Topic Draft");
  });

  it.each(["update", "delete"] as const)(
    "does not let a delayed old-Topic Question %s overwrite the new Topic",
    async (operation) => {
      const secondTopic = { ...topic, id: "topic-2", name: "Integrals" };
      const secondQuestion = { ...question, id: "question-2", topic_id: secondTopic.id, prompt: "Integrate x" };
      let resolveWrite: ((value: object) => void) | undefined;
      const pendingWrite = new Promise<object>((resolve) => { resolveWrite = resolve; });
      const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        const url = input.toString();
        if (operation === "update" && init?.method === "PATCH") return pendingWrite;
        if (operation === "delete" && init?.method === "DELETE") return pendingWrite;
        if (url.endsWith("/subjects")) return jsonResponse([subject]);
        if (url.endsWith("/subjects/subject-1/topics")) return jsonResponse([topic, secondTopic]);
        if (url.endsWith("/topics/topic-1/questions")) return jsonResponse([question]);
        if (url.endsWith("/topics/topic-2/questions")) return jsonResponse([secondQuestion]);
        if (url.endsWith("/topics/topic-1/mastery") || url.endsWith("/topics/topic-2/mastery")) return jsonResponse({ topic_id: topic.id, score: "0.00", updated_at: null });
        if (url.endsWith("/questions/question-1/attempts") || url.endsWith("/questions/question-2/attempts")) return jsonResponse([]);
        return jsonResponse({ error: { message: "Unexpected request" } }, 500);
      });
      vi.stubGlobal("fetch", fetchMock);
      vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
      vi.stubGlobal("prompt", vi.fn()
        .mockReturnValueOnce("Updated old question")
        .mockReturnValueOnce("Updated answer")
        .mockReturnValueOnce("hard"));
      renderPractice();

      await screen.findByText("Show answer reference");
      fireEvent.click(screen.getByRole("button", { name: operation === "update" ? "Edit" : "Delete" }));
      fireEvent.change(screen.getByLabelText("Practice topic"), { target: { value: secondTopic.id } });
      expect(await screen.findAllByText("Integrate x")).toHaveLength(2);

      resolveWrite?.(operation === "update"
        ? jsonResponse({ ...question, prompt: "Updated old question" })
        : ({ ok: true, status: 204, json: vi.fn() }));
      await waitFor(() => expect(screen.queryByText("Updated old question")).not.toBeInTheDocument());
      expect(screen.getAllByText("Integrate x")).toHaveLength(2);
    },
  );

  it("refreshes the planner for a successful old-context Attempt without contaminating the new Topic", async () => {
    const secondTopic = { ...topic, id: "topic-2", name: "Integrals" };
    const secondQuestion = { ...question, id: "question-2", topic_id: secondTopic.id, prompt: "Integrate x" };
    const onAttemptRecorded = vi.fn();
    let resolveAttempt: ((value: object) => void) | undefined;
    const pendingAttempt = new Promise<object>((resolve) => { resolveAttempt = resolve; });
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === "POST" && url.endsWith("/questions/question-1/attempts")) return pendingAttempt;
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/topics")) return jsonResponse([topic, secondTopic]);
      if (url.endsWith("/topics/topic-1/questions")) return jsonResponse([question]);
      if (url.endsWith("/topics/topic-2/questions")) return jsonResponse([secondQuestion]);
      if (url.endsWith("/topics/topic-1/mastery")) return jsonResponse({ topic_id: topic.id, score: "0.00", updated_at: null });
      if (url.endsWith("/topics/topic-2/mastery")) return jsonResponse({ topic_id: secondTopic.id, score: "70.00", updated_at: "2026-09-12T00:00:00Z" });
      if (url.endsWith("/questions/question-1/attempts") || url.endsWith("/questions/question-2/attempts")) return jsonResponse([]);
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPractice({ onAttemptRecorded });

    await screen.findByText("Show answer reference");
    fireEvent.click(screen.getByRole("button", { name: "Record attempt" }));
    fireEvent.change(screen.getByLabelText("Practice topic"), { target: { value: secondTopic.id } });
    await waitFor(() => expect(screen.getByLabelText("Current mastery")).toHaveTextContent("70.00"));

    resolveAttempt?.(jsonResponse({
      attempt: { id: "attempt-old", question_id: question.id, correct: true, hints_used: 0, solution_seen: false, time_spent_seconds: 0, created_at: "2026-09-12T00:00:00Z" },
      mastery: { topic_id: topic.id, score: "15.00", updated_at: "2026-09-12T00:00:00Z" },
    }, 201));
    await waitFor(() => expect(onAttemptRecorded).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText("Current mastery")).toHaveTextContent("70.00");
    expect(screen.queryByText("Attempt recorded. Mastery updated to 15.00.")).not.toBeInTheDocument();
    expect(screen.getAllByText("Integrate x")).toHaveLength(2);
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

function renderPractice({
  onAttemptRecorded,
  initialSubjectId = subject.id,
  initialTopicId = topic.id,
}: {
  onAttemptRecorded?: () => void;
  initialSubjectId?: string;
  initialTopicId?: string;
} = {}) {
  function Harness() {
    const [selection, setSelection] = useState({
      subjectId: initialSubjectId,
      topicId: initialTopicId,
    });
    return <PracticeManager
      selectedSubjectId={selection.subjectId}
      selectedTopicId={selection.topicId}
      academicRevision={0}
      onSubjectSelected={(subjectId) => setSelection({ subjectId, topicId: "" })}
      onTopicSelected={(subjectId, topicId) => setSelection({ subjectId, topicId })}
      onAttemptRecorded={onAttemptRecorded}
    />;
  }
  return render(<Harness />);
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
