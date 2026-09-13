import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LearningWorkspace } from "./learning-workspace";

vi.mock("./global-study-planner", () => ({
  GlobalStudyPlanner: ({ refreshRevision }: { refreshRevision: number }) => (
    <output aria-label="Planner revision">{refreshRevision}</output>
  ),
}));

vi.mock("./domain-manager", () => ({
  DomainManager: ({ onPlannerInputsChanged }: { onPlannerInputsChanged?: () => void }) => (
    <div>
      <button type="button" onClick={onPlannerInputsChanged}>Exam mutation</button>
      <button type="button" onClick={onPlannerInputsChanged}>ExamTopic mutation</button>
      <button type="button" onClick={onPlannerInputsChanged}>Relevant rename</button>
      <button type="button">Question mutation</button>
    </div>
  ),
}));

vi.mock("./practice-manager", () => ({
  PracticeManager: ({ onPlannerInputsChanged }: { onPlannerInputsChanged?: () => void }) => (
    <div>
      <button type="button" onClick={onPlannerInputsChanged}>Successful Attempt</button>
      <button type="button">Failed Attempt</button>
      <button type="button">Question Generation</button>
      <button type="button">Tutor</button>
    </div>
  ),
}));

vi.mock("./study-planner", () => ({ StudyPlanner: () => <div>Exam planner</div> }));

describe("LearningWorkspace", () => {
  afterEach(cleanup);

  it("refreshes only for planner-input mutations", () => {
    render(<LearningWorkspace />);
    const revision = screen.getByLabelText("Planner revision");
    expect(revision).toHaveTextContent("0");

    for (const name of [
      "Successful Attempt",
      "Exam mutation",
      "ExamTopic mutation",
      "Relevant rename",
    ]) {
      fireEvent.click(screen.getByRole("button", { name }));
    }
    expect(revision).toHaveTextContent("4");

    for (const name of [
      "Failed Attempt",
      "Question mutation",
      "Question Generation",
      "Tutor",
    ]) {
      fireEvent.click(screen.getByRole("button", { name }));
    }
    expect(revision).toHaveTextContent("4");
  });
});
