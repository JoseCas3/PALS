"use client";

import { useEffect, useState } from "react";

import { api } from "../lib/api";
import type { Exam, PlannerFactorCode, StudyPlan, Subject } from "../lib/types";

const factorLabels: Record<PlannerFactorCode, string> = {
  mastery_need: "Mastery need",
  urgency: "Exam urgency",
  exam_weight: "Exam weight",
};

export function StudyPlanner() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [subjectId, setSubjectId] = useState("");
  const [exams, setExams] = useState<Exam[]>([]);
  const [examId, setExamId] = useState("");
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [loadingSubjects, setLoadingSubjects] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void api
      .listSubjects()
      .then((items) => {
        setSubjects(items);
        setSubjectId(items[0]?.id ?? "");
      })
      .catch((reason: unknown) => setError(errorMessage(reason)))
      .finally(() => setLoadingSubjects(false));
  }, []);

  useEffect(() => {
    if (!subjectId) return;
    let ignore = false;
    void api
      .listExams(subjectId)
      .then((items) => {
        if (ignore) return;
        setExams(items);
        setExamId(items[0]?.id ?? "");
      })
      .catch((reason: unknown) => {
        if (!ignore) setError(errorMessage(reason));
      });
    return () => {
      ignore = true;
    };
  }, [subjectId]);

  function chooseSubject(nextSubjectId: string) {
    setSubjectId(nextSubjectId);
    setExams([]);
    setExamId("");
    setPlan(null);
    setError("");
  }

  function chooseExam(nextExamId: string) {
    setExamId(nextExamId);
    setPlan(null);
    setError("");
  }

  async function generatePlan() {
    if (!examId || generating) return;
    setGenerating(true);
    setError("");
    try {
      setPlan(await api.getStudyPlan(examId));
    } catch (reason) {
      setPlan(null);
      setError(errorMessage(reason));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <section className="panel space-y-5">
      <div>
        <p className="eyebrow">Adaptive study planner</p>
        <h2>What should I study for this exam?</h2>
      </div>

      {error && <p role="alert" className="error-banner">{error}</p>}

      {loadingSubjects ? <p className="empty">Loading study options…</p> : <>
        <div className="planner-controls">
          <select
            aria-label="Planner subject"
            value={subjectId}
            onChange={(event) => chooseSubject(event.target.value)}
          >
            <option value="">Choose a subject</option>
            {subjects.map((subject) => (
              <option key={subject.id} value={subject.id}>{subject.name}</option>
            ))}
          </select>
          <select
            aria-label="Planner exam"
            value={examId}
            onChange={(event) => chooseExam(event.target.value)}
            disabled={!subjectId || exams.length === 0}
          >
            <option value="">Choose an exam</option>
            {exams.map((exam) => (
              <option key={exam.id} value={exam.id}>{exam.name}</option>
            ))}
          </select>
          <button type="button" onClick={() => void generatePlan()} disabled={!examId || generating}>
            {generating ? "Generating…" : "Generate study plan"}
          </button>
        </div>

        {subjects.length === 0 && (
          <p className="empty">Create a subject and exam before generating a study plan.</p>
        )}
        {subjects.length > 0 && subjectId && exams.length === 0 && (
          <p className="empty">This subject has no exams yet.</p>
        )}
        {!plan && examId && !generating && !error && (
          <p className="empty">Choose Generate study plan to rank this Exam&apos;s Topics.</p>
        )}
      </>}

      {plan && <div aria-label="Study plan results">
        <div className="planner-result-heading">
          <div><h3>{plan.exam_name}</h3><p>Exam {new Date(plan.exam_date).toLocaleString()}</p></div>
          <p>Generated {new Date(plan.generated_at).toLocaleString()}</p>
        </div>
        {plan.items.length === 0 ? (
          <p className="empty">This Exam has no assigned Topics.</p>
        ) : (
          <ol className="plan-list">
            {plan.items.map((item, index) => (
              <li key={item.topic_id}>
                <div className="plan-rank" aria-label={`Rank ${index + 1}`}>{index + 1}</div>
                <div className="plan-content">
                  <div className="plan-title">
                    <h3>{item.topic_name}</h3>
                    <strong>Priority {item.priority}</strong>
                  </div>
                  <dl className="plan-metrics">
                    <div><dt>Mastery</dt><dd>{item.mastery_score}</dd></div>
                    <div><dt>Exam weight</dt><dd>{item.exam_weight}</dd></div>
                    <div><dt>Urgency</dt><dd>{item.urgency}</dd></div>
                  </dl>
                  <p className="plan-summary">{item.reason.summary}</p>
                  <details>
                    <summary>Calculation factors</summary>
                    <dl className="factor-list">
                      {item.reason.factors.map((factor) => (
                        <div key={factor.code}>
                          <dt>{factorLabels[factor.code]}</dt>
                          <dd>{factor.value} × {factor.formula_weight}</dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>}
    </section>
  );
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "Something went wrong";
}
