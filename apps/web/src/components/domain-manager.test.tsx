import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DomainManager } from "./domain-manager";

describe("DomainManager", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads and creates subjects", async () => {
    const fetchMock = vi.fn(async (_input: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "POST") {
        return jsonResponse({
          id: "subject-1",
          name: "Calculus",
          description: "",
          created_at: "2026-09-11T00:00:00Z",
          updated_at: "2026-09-11T00:00:00Z",
        }, 201);
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderDomain();

    await screen.findByText("Create your first subject to begin.");
    fireEvent.change(screen.getByLabelText("Subject name"), { target: { value: "Calculus" } });
    fireEvent.click(screen.getByRole("button", { name: "Add subject" }));

    expect((await screen.findAllByText("Calculus")).length).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/subjects",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("shows the API error message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ error: { message: "API failed" } }, 500)));
    renderDomain();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("API failed"));
  });

  it("assigns a weighted topic to an exam", async () => {
    const onPlannerInputsChanged = vi.fn();
    const subject = entity("subject-1", "Calculus");
    const topic = { ...entity("topic-1", "Limits"), subject_id: subject.id };
    const exam = {
      ...entity("exam-1", "Final"),
      subject_id: subject.id,
      exam_date: "2026-12-01T15:00:00Z",
    };
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = input.toString();
      if (init?.method === "PUT") {
        return jsonResponse({ exam_id: exam.id, topic_id: topic.id, weight: 0.5 });
      }
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/topics")) return jsonResponse([topic]);
      if (url.endsWith("/subjects/subject-1/exams")) return jsonResponse([exam]);
      if (url.endsWith("/exams/exam-1/topics")) return jsonResponse([]);
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderDomain({
      initialSubjectId: subject.id,
      onPlannerInputsChanged,
    });

    await screen.findByRole("heading", { name: "Weighted topics" });
    fireEvent.change(screen.getByLabelText("Topic to assign"), {
      target: { value: topic.id },
    });
    fireEvent.change(screen.getByLabelText("Topic weight"), { target: { value: "0.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Save weight" }));

    await screen.findByText("Weight 0.5");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/exams/exam-1/topics/topic-1",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(onPlannerInputsChanged).toHaveBeenCalledTimes(1);
  });
});

function renderDomain({
  initialSubjectId = "",
  initialTopicId = "",
  onPlannerInputsChanged,
  onAcademicDataChanged,
}: {
  initialSubjectId?: string;
  initialTopicId?: string;
  onPlannerInputsChanged?: () => void;
  onAcademicDataChanged?: () => void;
} = {}) {
  function Harness() {
    const [selection, setSelection] = useState({
      subjectId: initialSubjectId,
      topicId: initialTopicId,
    });
    return <DomainManager
      selectedSubjectId={selection.subjectId}
      selectedTopicId={selection.topicId}
      onSubjectSelected={(subjectId) => setSelection({ subjectId, topicId: "" })}
      onTopicSelected={(subjectId, topicId) => setSelection({ subjectId, topicId })}
      onAcademicDataChanged={onAcademicDataChanged}
      onPlannerInputsChanged={onPlannerInputsChanged}
    />;
  }
  return render(<Harness />);
}

function jsonResponse(payload: object, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(payload) };
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
