import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GlobalStudyPlanner } from "./global-study-planner";

describe("GlobalStudyPlanner", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads initially, emphasizes the first item, and preserves server order and context", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(planResponse()));
    vi.stubGlobal("fetch", fetchMock);
    const { container } = render(<GlobalStudyPlanner refreshRevision={0} />);

    expect(screen.getByText("Loading your active study workload…")).toBeInTheDocument();
    expect(await screen.findByLabelText("Study this now")).toHaveTextContent("Calculus");
    expect(screen.getByLabelText("Study this now")).toHaveTextContent("First from server");
    expect(screen.getByLabelText("Study this now")).toHaveTextContent("Midterm");
    expect(screen.getByLabelText("Study this now")).toHaveTextContent("Mastery40.00");
    expect(screen.getByLabelText("Study this now")).toHaveTextContent("Priority 0.4000");
    expect(screen.getByLabelText("Study this now")).toHaveTextContent(
      "Mastery need is the strongest contributor",
    );
    const text = container.textContent ?? "";
    expect(text.indexOf("Second from server")).toBeLessThan(text.indexOf("Third from server"));
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/study-plan",
      expect.any(Object),
    );
  });

  it("renders the same Topic once per Exam and handles an empty plan", async () => {
    const duplicate = planItem("exam-2", "topic-1", "Same topic", "Final", "0.9000");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ ...planResponse(), items: [planResponse().items[0], duplicate] }),
      ),
    );
    render(<GlobalStudyPlanner refreshRevision={0} />);
    expect(await screen.findAllByText(/First from server|Same topic/)).toHaveLength(2);
    expect(screen.getByText("Midterm", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Final", { exact: false })).toBeInTheDocument();

    cleanup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ ...planResponse(), items: [] })),
    );
    render(<GlobalStudyPlanner refreshRevision={0} />);
    expect(await screen.findByText("No active Exam Topics to study right now.")).toBeInTheDocument();
  });

  it("shows errors, retries, manually refreshes, and blocks duplicate manual refresh", async () => {
    let calls = 0;
    let resolveRefresh: ((value: object) => void) | undefined;
    const pendingRefresh = new Promise<object>((resolve) => {
      resolveRefresh = resolve;
    });
    const fetchMock = vi.fn(() => {
      calls += 1;
      if (calls === 1) return Promise.resolve(jsonResponse({ error: { message: "Failed" } }, 500));
      if (calls === 2) return Promise.resolve(jsonResponse(planResponse()));
      return pendingRefresh;
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<GlobalStudyPlanner refreshRevision={0} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Failed");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByText("First from server");
    fireEvent.click(screen.getByRole("button", { name: "Refresh plan" }));
    const refreshing = screen.getByRole("button", { name: "Refreshing…" });
    expect(refreshing).toBeDisabled();
    fireEvent.click(refreshing);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    resolveRefresh?.(jsonResponse(planResponse()));
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh plan" })).toBeEnabled());
  });

  it("ignores stale successes and stale errors after a revision refresh", async () => {
    let resolveFirst: ((value: object) => void) | undefined;
    let rejectThird: ((reason: Error) => void) | undefined;
    const first = new Promise<object>((resolve) => {
      resolveFirst = resolve;
    });
    const third = new Promise<object>((_resolve, reject) => {
      rejectThird = reject;
    });
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(first)
      .mockResolvedValueOnce(jsonResponse(planResponse("Newest")))
      .mockReturnValueOnce(third)
      .mockResolvedValueOnce(jsonResponse(planResponse("Newest again")));
    vi.stubGlobal("fetch", fetchMock);
    const { rerender } = render(<GlobalStudyPlanner refreshRevision={0} />);

    rerender(<GlobalStudyPlanner refreshRevision={1} />);
    await screen.findByText("Newest");
    resolveFirst?.(jsonResponse(planResponse("Stale")));
    await waitFor(() => expect(screen.queryByText("Stale")).not.toBeInTheDocument());

    rerender(<GlobalStudyPlanner refreshRevision={2} />);
    rerender(<GlobalStudyPlanner refreshRevision={3} />);
    await screen.findByText("Newest again");
    rejectThird?.(new Error("Stale error"));
    await waitFor(() => expect(screen.queryByText("Stale error")).not.toBeInTheDocument());
  });
});

function planResponse(firstName = "First from server") {
  return {
    generated_at: "2026-09-12T15:00:00Z",
    items: [
      planItem("exam-1", "topic-1", firstName, "Midterm", "0.4000"),
      planItem("exam-2", "topic-2", "Second from server", "Final", "0.9000"),
      planItem("exam-3", "topic-3", "Third from server", "Quiz", "0.8000"),
    ],
  };
}

function planItem(
  examId: string,
  topicId: string,
  topicName: string,
  examName: string,
  priority: string,
) {
  return {
    subject_id: "subject-1",
    subject_name: "Calculus",
    exam_id: examId,
    exam_name: examName,
    exam_date: "2026-09-27T15:00:00Z",
    topic_id: topicId,
    topic_name: topicName,
    mastery_score: "40.00",
    mastery_need: "0.6000",
    urgency: "0.5000",
    exam_weight: "0.8000",
    priority,
    reason: {
      summary: "Mastery need is the strongest contributor to this priority.",
      factors: [
        { code: "mastery_need", value: "0.6000", formula_weight: "0.5000" },
        { code: "urgency", value: "0.5000", formula_weight: "0.3000" },
        { code: "exam_weight", value: "0.8000", formula_weight: "0.2000" },
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
