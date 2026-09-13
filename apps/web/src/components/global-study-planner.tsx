"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../lib/api";
import type { GlobalStudyPlan, GlobalStudyPlanItem } from "../lib/types";

type GlobalStudyPlannerProps = {
  refreshRevision: number;
  onPracticeTopicRequested?: (subjectId: string, topicId: string) => void;
};

export function GlobalStudyPlanner({
  refreshRevision,
  onPracticeTopicRequested,
}: GlobalStudyPlannerProps) {
  const [plan, setPlan] = useState<GlobalStudyPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestGeneration = useRef(0);
  const loadingRef = useRef(false);

  const loadPlan = useCallback(async (supersede: boolean) => {
    if (!supersede && loadingRef.current) return;
    const generation = ++requestGeneration.current;
    loadingRef.current = true;
    setLoading(true);
    setError("");
    try {
      const nextPlan = await api.getGlobalStudyPlan();
      if (generation !== requestGeneration.current) return;
      setPlan(nextPlan);
    } catch (reason) {
      if (generation !== requestGeneration.current) return;
      setError(errorMessage(reason));
    } finally {
      if (generation === requestGeneration.current) {
        loadingRef.current = false;
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void loadPlan(true));
  }, [loadPlan, refreshRevision]);

  const recommendation = plan?.items[0];
  const upcoming = plan?.items.slice(1) ?? [];

  return (
    <section className="panel space-y-5" aria-label="Global Study Plan">
      <div className="global-plan-heading">
        <div>
          <p className="eyebrow">Global adaptive planner</p>
          <h2>What should I study now?</h2>
        </div>
        <button
          type="button"
          className="refresh-plan"
          disabled={loading}
          onClick={() => void loadPlan(false)}
        >
          {loading ? "Refreshing…" : "Refresh plan"}
        </button>
      </div>

      {error && (
        <div>
          <p role="alert" className="error-banner">{error}</p>
          <button type="button" className="refresh-plan" onClick={() => void loadPlan(false)}>
            Retry
          </button>
        </div>
      )}

      {loading && !plan && <p className="empty">Loading your active study workload…</p>}

      {!loading && !error && plan?.items.length === 0 && (
        <p className="empty">
          No active assigned Topics yet. Create a future Exam and assign Topics in Academic setup.
        </p>
      )}

      {recommendation && (
        <div aria-label="Study this now">
          <h3 className="global-plan-section-title">Study this now</h3>
          <PlanItem
            item={recommendation}
            emphasized
            onPracticeTopicRequested={onPracticeTopicRequested}
          />
        </div>
      )}

      {upcoming.length > 0 && (
        <div aria-label="Up next">
          <h3 className="global-plan-section-title">Up next</h3>
          <ol className="plan-list">
            {upcoming.map((item, index) => (
              <li key={`${item.exam_id}:${item.topic_id}`}>
                <div className="plan-rank" aria-label={`Rank ${index + 2}`}>{index + 2}</div>
                <PlanItemContent
                  item={item}
                  onPracticeTopicRequested={onPracticeTopicRequested}
                />
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

function PlanItem({
  item,
  emphasized,
  onPracticeTopicRequested,
}: {
  item: GlobalStudyPlanItem;
  emphasized: boolean;
  onPracticeTopicRequested?: (subjectId: string, topicId: string) => void;
}) {
  return (
    <article className={emphasized ? "global-recommendation" : undefined}>
      <PlanItemContent
        item={item}
        onPracticeTopicRequested={onPracticeTopicRequested}
      />
    </article>
  );
}

function PlanItemContent({
  item,
  onPracticeTopicRequested,
}: {
  item: GlobalStudyPlanItem;
  onPracticeTopicRequested?: (subjectId: string, topicId: string) => void;
}) {
  return (
    <div className="plan-content">
      <div className="plan-title">
        <div>
          <p className="plan-context">{item.subject_name}</p>
          <h3>{item.topic_name}</h3>
        </div>
        <strong>Priority {item.priority}</strong>
      </div>
      <p className="plan-exam">
        {item.exam_name} · {new Date(item.exam_date).toLocaleString()}
      </p>
      <dl className="plan-metrics global-plan-metrics">
        <div><dt>Mastery</dt><dd>{item.mastery_score}</dd></div>
        <div><dt>Priority</dt><dd>{item.priority}</dd></div>
      </dl>
      <p className="plan-summary">{item.reason.summary}</p>
      <button
        type="button"
        className="practice-topic-action"
        onClick={() => onPracticeTopicRequested?.(item.subject_id, item.topic_id)}
      >
        Practice this topic
      </button>
    </div>
  );
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "Something went wrong";
}
