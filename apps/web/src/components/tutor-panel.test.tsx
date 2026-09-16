import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TutorPanel } from "./tutor-panel";

describe("TutorPanel", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("selects a level, prevents duplicates, and safely renders plain text", async () => {
    let resolveRequest: ((value: object) => void) | undefined;
    const pending = new Promise<object>((resolve) => {
      resolveRequest = resolve;
    });
    const fetchMock = vi.fn(() => pending);
    vi.stubGlobal("fetch", fetchMock);
    render(<TutorPanel questionId="question-1" />);

    fireEvent.click(screen.getByRole("radio", { name: /5\. Guided/ }));
    fireEvent.click(screen.getByRole("button", { name: "Get help" }));
    expect(screen.getByRole("radio", { name: /5\. Guided/ })).toBeDisabled();
    expect(screen.getByRole("radio", { name: /2\. Principle/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: /2\. Principle/ }));
    expect(screen.getByRole("radio", { name: /5\. Guided/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    fireEvent.click(screen.getByRole("button", { name: "Getting help…" }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/questions/question-1/tutor",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ help_level: 5 }) }),
    );

    resolveRequest?.(jsonResponse({ content: "Step one\n<script>alert(1)</script>" }));
    const response = await screen.findByLabelText("Tutor response");
    expect(response).toHaveTextContent("Step one");
    expect(response.querySelector("script")).toBeNull();
  });

  it("shows service errors and clears state when the question changes", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ error: { message: "Tutor service is temporarily unavailable" } }, 503),
    );
    vi.stubGlobal("fetch", fetchMock);
    const view = render(<TutorPanel questionId="question-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Get help" }));
    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent("temporarily unavailable");

    view.rerender(<TutorPanel questionId="question-2" />);
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(screen.getByRole("radio", { name: /1\. Concept/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("requests grounded help and renders single and multi-page sources", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        outcome: "ANSWER",
        answer: "A grounded hint.",
        content: "A grounded hint.",
        citations: [
          {
            alias: "S1",
            document_filename: "notes.pdf",
            page_start: 3,
            page_end: 3,
          },
          {
            alias: "S2",
            document_filename: "chapter.pdf",
            page_start: 4,
            page_end: 6,
          },
        ],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<TutorPanel questionId="question-1" />);

    fireEvent.click(screen.getByLabelText("Ground this answer in my Subject documents"));
    fireEvent.click(screen.getByRole("button", { name: "Get help" }));

    expect(await screen.findByLabelText("Tutor response")).toHaveTextContent(
      "A grounded hint.",
    );
    expect(screen.getByLabelText("Tutor sources")).toHaveTextContent(
      "S1 — notes.pdf, p. 3",
    );
    expect(screen.getByLabelText("Tutor sources")).toHaveTextContent(
      "S2 — chapter.pdf, pp. 4–6",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/questions/question-1/tutor",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ help_level: 1, grounding_mode: "REQUIRED" }),
      }),
    );
  });

  it("renders explicit insufficient evidence without a fake empty answer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          outcome: "INSUFFICIENT_EVIDENCE",
          answer: null,
          content: null,
          citations: [],
        }),
      ),
    );
    render(<TutorPanel questionId="question-1" />);

    fireEvent.click(screen.getByLabelText("Ground this answer in my Subject documents"));
    fireEvent.click(screen.getByRole("button", { name: "Get help" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "do not contain sufficient evidence",
    );
    expect(screen.queryByLabelText("Tutor response")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Tutor sources")).not.toBeInTheDocument();
  });
});

function jsonResponse(payload: object, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  };
}
