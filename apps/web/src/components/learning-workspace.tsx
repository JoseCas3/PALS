"use client";

import { useCallback, useState } from "react";

import { DomainManager } from "./domain-manager";
import { GlobalStudyPlanner } from "./global-study-planner";
import { PracticeManager } from "./practice-manager";
import { StudyPlanner } from "./study-planner";

export function LearningWorkspace() {
  const [plannerRevision, setPlannerRevision] = useState(0);
  const refreshGlobalPlan = useCallback(() => {
    setPlannerRevision((revision) => revision + 1);
  }, []);

  return (
    <>
      <GlobalStudyPlanner refreshRevision={plannerRevision} />
      <div className="mt-6">
        <DomainManager onPlannerInputsChanged={refreshGlobalPlan} />
      </div>
      <div className="mt-6">
        <PracticeManager onPlannerInputsChanged={refreshGlobalPlan} />
      </div>
      <div className="mt-6"><StudyPlanner /></div>
    </>
  );
}
