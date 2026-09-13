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
});

function jsonResponse(payload: object, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  };
}
