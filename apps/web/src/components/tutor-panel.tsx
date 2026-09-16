"use client";

import { useState } from "react";

import { api } from "../lib/api";
import type { GroundedCitation } from "../lib/types";

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
  const [citations, setCitations] = useState<GroundedCitation[]>([]);
  const [groundingRequired, setGroundingRequired] = useState(false);
  const [insufficient, setInsufficient] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function requestHelp() {
    if (loading) return;
    setLoading(true);
    setContent("");
    setCitations([]);
    setInsufficient(false);
    setError("");
    try {
      const result = await api.getTutorHelp(questionId, helpLevel, groundingRequired);
      if (result.outcome === "INSUFFICIENT_EVIDENCE") {
        setInsufficient(true);
      } else {
        setContent(result.answer ?? result.content ?? "");
        setCitations(result.citations ?? []);
      }
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
            disabled={loading}
            className={helpLevel === level.value ? "selected" : ""}
            onClick={() => setHelpLevel(level.value)}
          >
            <strong>{level.value}. {level.name}</strong>
            <span>{level.description}</span>
          </button>
        ))}
      </div>
      <label className="tutor-grounding-option">
        <input
          type="checkbox"
          checked={groundingRequired}
          disabled={loading}
          onChange={(event) => setGroundingRequired(event.target.checked)}
        />
        Ground this answer in my Subject documents
      </label>
      {error && <p role="alert" className="error-banner">{error}</p>}
      {insufficient && (
        <p role="status" className="empty-state">
          The available Subject documents do not contain sufficient evidence for this request.
        </p>
      )}
      {content && <div className="tutor-response" aria-label="Tutor response">{content}</div>}
      {citations.length > 0 && (
        <div className="tutor-sources" aria-label="Tutor sources">
          <strong>Sources</strong>
          <ul>
            {citations.map((citation) => (
              <li key={citation.alias}>
                {citation.alias} — {citation.document_filename}, {formatPages(citation)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function formatPages(citation: GroundedCitation) {
  return citation.page_start === citation.page_end
    ? `p. ${citation.page_start}`
    : `pp. ${citation.page_start}–${citation.page_end}`;
}
