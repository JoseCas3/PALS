import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StudyPlanner } from "./study-planner";

const subject = entity("subject-1", "Calculus");
const firstExam = exam("exam-1", "Final");
const secondExam = exam("exam-2", "Retake");

describe("StudyPlanner", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("preserves server order and renders every factor", async () => {
    vi.stubGlobal("fetch", standardFetch(planResponse()));
    const { container } = render(<StudyPlanner />);

    const button = await enabledGenerateButton();
    fireEvent.click(button);

    await screen.findByText("First from server");
    const text = container.textContent ?? "";
    expect(text.indexOf("First from server")).toBeLessThan(text.indexOf("Second from server"));
    expect(screen.getByText("Priority 0.4000")).toBeInTheDocument();
    expect(screen.getAllByText("Mastery need")).toHaveLength(2);
    expect(screen.getAllByText("Exam urgency")).toHaveLength(2);
    expect(screen.getAllByText("Exam weight")).toHaveLength(4);
    expect(screen.getAllByText("0.6000 × 0.5000")).toHaveLength(2);
  });

  it("prevents duplicate generation while loading", async () => {
    let resolvePlan: ((value: object) => void) | undefined;
    const pendingPlan = new Promise<object>((resolve) => {
      resolvePlan = resolve;
    });
    const fetchMock = standardFetch(planResponse(), pendingPlan);
    vi.stubGlobal("fetch", fetchMock);
    render(<StudyPlanner />);

    const button = await enabledGenerateButton();
    fireEvent.click(button);
    fireEvent.click(screen.getByRole("button", { name: "Generating…" }));
    expect(screen.getByRole("button", { name: "Generating…" })).toBeDisabled();
    expect(planCalls(fetchMock)).toHaveLength(1);

    resolvePlan?.(jsonResponse(planResponse()));
    await screen.findByText("First from server");
  });

  it("clears a stale plan when the Exam changes", async () => {
    vi.stubGlobal("fetch", standardFetch(planResponse(), undefined, [firstExam, secondExam]));
    render(<StudyPlanner />);

    fireEvent.click(await enabledGenerateButton());
    await screen.findByText("First from server");
    fireEvent.change(screen.getByLabelText("Planner exam"), {
      target: { value: secondExam.id },
    });

    expect(screen.queryByText("First from server")).not.toBeInTheDocument();
    expect(screen.getByText("Choose Generate study plan to rank this Exam's Topics."))
      .toBeInTheDocument();
  });

  it("ignores a delayed plan after the Exam changes", async () => {
    let resolvePlan: ((value: object) => void) | undefined;
    const pendingPlan = new Promise<object>((resolve) => { resolvePlan = resolve; });
    vi.stubGlobal("fetch", standardFetch(planResponse(), pendingPlan, [firstExam, secondExam]));
    render(<StudyPlanner />);

    fireEvent.click(await enabledGenerateButton());
    fireEvent.change(screen.getByLabelText("Planner exam"), { target: { value: secondExam.id } });
    resolvePlan?.(jsonResponse(planResponse()));

    await waitFor(() => expect(screen.queryByText("First from server")).not.toBeInTheDocument());
    expect(screen.getByLabelText("Planner exam")).toHaveValue(secondExam.id);
  });

  it("renders an empty plan", async () => {
    vi.stubGlobal("fetch", standardFetch({ ...planResponse(), items: [] }));
    render(<StudyPlanner />);

    fireEvent.click(await enabledGenerateButton());
    expect(await screen.findByText("This Exam has no assigned Topics.")).toBeInTheDocument();
  });

  it("renders the past Exam API error", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.endsWith("/subjects")) return jsonResponse([subject]);
      if (url.endsWith("/subjects/subject-1/exams")) return jsonResponse([firstExam]);
      if (url.endsWith("/exams/exam-1/study-plan")) {
        return jsonResponse(
          { error: { message: "Study plans cannot be generated for a past exam" } },
          409,
        );
      }
      return jsonResponse({ error: { message: "Unexpected request" } }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<StudyPlanner />);

    fireEvent.click(await enabledGenerateButton());
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Study plans cannot be generated for a past exam",
    );
  });

  it("handles no Subjects and no Exams", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));
    render(<StudyPlanner />);
    expect(
      await screen.findByText("Create a subject and exam before generating a study plan."),
    ).toBeInTheDocument();

    cleanup();
    vi.stubGlobal("fetch", standardFetch(planResponse(), undefined, []));
    render(<StudyPlanner />);
    expect(await screen.findByText("This subject has no exams yet.")).toBeInTheDocument();
  });
});

async function enabledGenerateButton() {
  const button = await screen.findByRole("button", { name: "Generate study plan" });
  await waitFor(() => expect(button).toBeEnabled());
  return button;
}

function standardFetch(
  plan: object,
  pendingPlan?: Promise<object>,
  exams = [firstExam],
) {
  return vi.fn(async (input: string | URL | Request) => {
    const url = input.toString();
    if (url.endsWith("/subjects")) return jsonResponse([subject]);
    if (url.endsWith("/subjects/subject-1/exams")) return jsonResponse(exams);
    if (url.endsWith("/exams/exam-1/study-plan")) {
      return pendingPlan ?? jsonResponse(plan);
    }
    return jsonResponse({ error: { message: "Unexpected request" } }, 500);
  });
}

function planCalls(mock: ReturnType<typeof vi.fn>) {
  return mock.mock.calls.filter(([input]) => input.toString().endsWith("/study-plan"));
}

function planResponse() {
  return {
    exam_id: firstExam.id,
    exam_name: firstExam.name,
    exam_date: firstExam.exam_date,
    generated_at: "2026-09-11T12:00:00Z",
    items: [
      planItem("topic-1", "First from server", "0.4000"),
      planItem("topic-2", "Second from server", "0.9000"),
    ],
  };
}

function planItem(id: string, name: string, priority: string) {
  return {
    topic_id: id,
    topic_name: name,
    mastery_score: "40.00",
    mastery_need: "0.6000",
    urgency: "0.5000",
    exam_weight: "0.5000",
    priority,
    reason: {
      summary: "Mastery need is the strongest contributor to this priority.",
      factors: [
        { code: "mastery_need", value: "0.6000", formula_weight: "0.5000" },
        { code: "urgency", value: "0.5000", formula_weight: "0.3000" },
        { code: "exam_weight", value: "0.5000", formula_weight: "0.2000" },
      ],
    },
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

function exam(id: string, name: string) {
  return {
    ...entity(id, name),
    subject_id: subject.id,
    exam_date: "2026-10-01T12:00:00Z",
  };
}
