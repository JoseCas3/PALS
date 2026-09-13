"use client";

import { useState } from "react";

import { api } from "../lib/api";

const levels = [
  { value: 1, name: "Concept", description: "One conceptual hint" },
  { value: 2, name: "Principle", description: "Relevant rule or formula" },
  { value: 3, name: "Strategy", description: "An approach without the first step" },
  { value: 4, name: "First step", description: "Only the first concrete step" },
  { value: 5, name: "Guided", description: "Staged guidance without the final answer" },
  { value: 6, name: "Full solution", description: "Complete reasoning and answer" },
];

export function TutorPanel({ questionId }: { questionId: string }) {
  return <TutorPanelState key={questionId} questionId={questionId} />;
}

function TutorPanelState({ questionId }: { questionId: string }) {
  const [helpLevel, setHelpLevel] = useState(1);
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function requestHelp() {
    if (loading) return;
    setLoading(true);
    setContent("");
    setError("");
    try {
      const result = await api.getTutorHelp(questionId, helpLevel);
      setContent(result.content);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Tutor is unavailable");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="tutor-panel">
      <div className="tutor-heading">
        <div>
          <p className="eyebrow">Question tutor</p>
          <h3>Choose how much help you need</h3>
        </div>
        <button type="button" onClick={() => void requestHelp()} disabled={loading}>
          {loading ? "Getting help…" : "Get help"}
        </button>
      </div>
      <div className="help-levels" role="radiogroup" aria-label="Tutor help level">
        {levels.map((level) => (
          <button
            key={level.value}
            type="button"
            role="radio"
            aria-checked={helpLevel === level.value}
            className={helpLevel === level.value ? "selected" : ""}
            onClick={() => setHelpLevel(level.value)}
          >
            <strong>{level.value}. {level.name}</strong>
            <span>{level.description}</span>
          </button>
        ))}
      </div>
      {error && <p role="alert" className="error-banner">{error}</p>}
      {content && <div className="tutor-response" aria-label="Tutor response">{content}</div>}
    </div>
  );
}
