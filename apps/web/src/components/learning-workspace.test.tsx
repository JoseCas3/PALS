import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LearningWorkspace } from "./learning-workspace";

vi.mock("./global-study-planner", () => ({
  GlobalStudyPlanner: ({ refreshRevision, onPracticeTopicRequested }: {
    refreshRevision: number;
    onPracticeTopicRequested: (subjectId: string, topicId: string) => void;
  }) => <div>
    <output aria-label="Planner revision">{refreshRevision}</output>
    <button type="button" onClick={() => onPracticeTopicRequested("subject-2", "topic-2")}>Planner topic</button>
  </div>,
}));

vi.mock("./domain-manager", () => ({
  DomainManager: ({
    selectedSubjectId,
    selectedTopicId,
    onSubjectSelected,
    onTopicSelected,
    onAcademicDataChanged,
    onPlannerInputsChanged,
  }: {
    selectedSubjectId: string;
    selectedTopicId: string;
    onSubjectSelected: (subjectId: string) => void;
    onTopicSelected: (subjectId: string, topicId: string) => void;
    onAcademicDataChanged: () => void;
    onPlannerInputsChanged: () => void;
  }) => <div>
    <output aria-label="Domain selection">{selectedSubjectId}:{selectedTopicId}</output>
    <button type="button" onClick={() => onTopicSelected("subject-1", "topic-1")}>Domain topic</button>
    <button type="button" onClick={() => onSubjectSelected("subject-3")}>Change subject</button>
    <button type="button" onClick={onAcademicDataChanged}>Academic mutation</button>
    <button type="button" onClick={onPlannerInputsChanged}>Exam mutation</button>
  </div>,
}));

vi.mock("./practice-manager", () => ({
  PracticeManager: ({
    selectedSubjectId,
    selectedTopicId,
    academicRevision,
    onAttemptRecorded,
  }: {
    selectedSubjectId: string;
    selectedTopicId: string;
    academicRevision: number;
    onAttemptRecorded: () => void;
  }) => <div>
    <output aria-label="Practice selection">{selectedSubjectId}:{selectedTopicId}</output>
    <output aria-label="Practice academic revision">{academicRevision}</output>
    <button type="button" onClick={onAttemptRecorded}>Successful Attempt</button>
    <button type="button">Failed Attempt</button>
    <button type="button">Question Generation</button>
    <button type="button">Tutor</button>
  </div>,
}));

vi.mock("./study-planner", () => ({
  StudyPlanner: ({ academicRevision }: { academicRevision: number }) =>
    <output aria-label="Planner academic revision">{academicRevision}</output>,
}));

describe("LearningWorkspace", () => {
  afterEach(cleanup);

  it("coordinates planner and Domain Topic selection with Practice", () => {
    render(<LearningWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: "Planner topic" }));
    expect(screen.getByLabelText("Practice selection")).toHaveTextContent("subject-2:topic-2");
    expect(screen.getByLabelText("Domain selection")).toHaveTextContent("subject-2:topic-2");

    fireEvent.click(screen.getByRole("button", { name: "Domain topic" }));
    expect(screen.getByLabelText("Practice selection")).toHaveTextContent("subject-1:topic-1");

    fireEvent.click(screen.getByRole("button", { name: "Change subject" }));
    expect(screen.getByLabelText("Practice selection")).toHaveTextContent("subject-3:");
  });

  it("publishes academic revisions and refreshes only for planner inputs", () => {
    render(<LearningWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "Academic mutation" }));
    expect(screen.getByLabelText("Practice academic revision")).toHaveTextContent("1");
    expect(screen.getByLabelText("Planner academic revision")).toHaveTextContent("1");

    fireEvent.click(screen.getByRole("button", { name: "Successful Attempt" }));
    fireEvent.click(screen.getByRole("button", { name: "Exam mutation" }));
    expect(screen.getByLabelText("Planner revision")).toHaveTextContent("2");

    for (const name of ["Failed Attempt", "Question Generation", "Tutor"]) {
      fireEvent.click(screen.getByRole("button", { name }));
    }
    expect(screen.getByLabelText("Planner revision")).toHaveTextContent("2");
  });
});
