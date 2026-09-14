"use client";

import { useCallback, useState } from "react";

import { DomainManager } from "./domain-manager";
import { DocumentManager } from "./document-manager";
import { GlobalStudyPlanner } from "./global-study-planner";
import { PracticeManager } from "./practice-manager";
import { StudyPlanner } from "./study-planner";

export type PracticeSelection = {
  subjectId: string;
  topicId: string;
};

export function LearningWorkspace() {
  const [plannerRevision, setPlannerRevision] = useState(0);
  const [academicRevision, setAcademicRevision] = useState(0);
  const [practiceSelection, setPracticeSelection] = useState<PracticeSelection>({
    subjectId: "",
    topicId: "",
  });

  const refreshGlobalPlan = useCallback(() => {
    setPlannerRevision((revision) => revision + 1);
  }, []);
  const refreshAcademicData = useCallback(() => {
    setAcademicRevision((revision) => revision + 1);
  }, []);
  const selectSubject = useCallback((subjectId: string) => {
    setPracticeSelection((current) =>
      current.subjectId === subjectId
        ? current
        : { subjectId, topicId: "" },
    );
  }, []);
  const selectTopic = useCallback((subjectId: string, topicId: string) => {
    setPracticeSelection({ subjectId, topicId });
  }, []);

  return (
    <>
      <GlobalStudyPlanner
        refreshRevision={plannerRevision}
        onPracticeTopicRequested={selectTopic}
      />
      <div className="mt-6">
        <PracticeManager
          selectedSubjectId={practiceSelection.subjectId}
          selectedTopicId={practiceSelection.topicId}
          academicRevision={academicRevision}
          onSubjectSelected={selectSubject}
          onTopicSelected={selectTopic}
          onAttemptRecorded={refreshGlobalPlan}
        />
      </div>
      <div className="mt-6">
        <DomainManager
          selectedSubjectId={practiceSelection.subjectId}
          selectedTopicId={practiceSelection.topicId}
          onSubjectSelected={selectSubject}
          onTopicSelected={selectTopic}
          onAcademicDataChanged={refreshAcademicData}
          onPlannerInputsChanged={refreshGlobalPlan}
        />
      </div>
      <div className="mt-6">
        <DocumentManager selectedSubjectId={practiceSelection.subjectId} />
      </div>
      <div className="mt-6"><StudyPlanner academicRevision={academicRevision} /></div>
    </>
  );
}
