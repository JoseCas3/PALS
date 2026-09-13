"use client";

import { FormEvent, useEffect, useLayoutEffect, useRef, useState } from "react";

import { api } from "../lib/api";
import type {
  Attempt,
  GenerationDifficulty,
  Mastery,
  Question,
  QuestionDifficulty,
  QuestionGenerationCandidate,
  Subject,
  Topic,
} from "../lib/types";
import { TutorPanel } from "./tutor-panel";

const emptyQuestion = {
  prompt: "",
  answerReference: "",
  difficulty: "medium" as QuestionDifficulty,
};
const emptyAttempt = {
  correct: "true",
  hintsUsed: "0",
  solutionSeen: false,
  timeSpentSeconds: "0",
};

type PracticeManagerProps = {
  selectedSubjectId: string;
  selectedTopicId: string;
  academicRevision: number;
  onSubjectSelected: (subjectId: string) => void;
  onTopicSelected: (subjectId: string, topicId: string) => void;
  onAttemptRecorded?: () => void;
};

export function PracticeManager({
  selectedSubjectId,
  selectedTopicId,
  academicRevision,
  onSubjectSelected,
  onTopicSelected,
  onAttemptRecorded,
}: PracticeManagerProps) {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loadedTopicId, setLoadedTopicId] = useState("");
  const [questionId, setQuestionId] = useState("");
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [mastery, setMastery] = useState<Mastery | null>(null);
  const [questionForm, setQuestionForm] = useState(emptyQuestion);
  const [attemptForm, setAttemptForm] = useState(emptyAttempt);
  const [submittingQuestion, setSubmittingQuestion] = useState(false);
  const [submittingAttempt, setSubmittingAttempt] = useState(false);
  const [generationCount, setGenerationCount] = useState("5");
  const [generationDifficulty, setGenerationDifficulty] =
    useState<GenerationDifficulty>("mixed");
  const [generatedCandidates, setGeneratedCandidates] = useState<
    QuestionGenerationCandidate[]
  >([]);
  const [generating, setGenerating] = useState(false);
  const [generationError, setGenerationError] = useState("");
  const [loadingSubjects, setLoadingSubjects] = useState(true);
  const [loadingTopics, setLoadingTopics] = useState(false);
  const [loadingPractice, setLoadingPractice] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  const contextGeneration = useRef(0);
  const generationRequest = useRef(0);
  const attemptHistoryRevision = useRef(0);
  const subjectRequest = useRef(0);
  const topicRequest = useRef(0);
  const activeTopicId = useRef(selectedTopicId);
  const activeQuestionId = useRef(questionId);
  useLayoutEffect(() => {
    activeTopicId.current = selectedTopicId;
  }, [selectedTopicId]);
  useLayoutEffect(() => {
    activeQuestionId.current = questionId;
  }, [questionId]);

  const visibleQuestions = loadedTopicId === selectedTopicId ? questions : [];
  const visibleMastery = loadedTopicId === selectedTopicId ? mastery : null;
  const selectedQuestion = visibleQuestions.find((item) => item.id === questionId);
  const selectedSubject = subjects.find((item) => item.id === selectedSubjectId);
  const selectedTopic = topics.find((item) => item.id === selectedTopicId);

  useEffect(() => {
    const request = ++subjectRequest.current;
    queueMicrotask(() => {
      if (request === subjectRequest.current) setLoadingSubjects(true);
    });
    void api
      .listSubjects()
      .then((items) => {
        if (request !== subjectRequest.current) return;
        setSubjects(items);
      })
      .catch((reason: unknown) => {
        if (request === subjectRequest.current) setError(errorMessage(reason));
      })
      .finally(() => {
        if (request === subjectRequest.current) setLoadingSubjects(false);
      });
  }, [academicRevision]);

  useEffect(() => {
    const request = ++topicRequest.current;
    queueMicrotask(() => {
      if (request !== topicRequest.current) return;
      setTopics([]);
      setLoadingTopics(Boolean(selectedSubjectId));
    });
    if (!selectedSubjectId) {
      return;
    }
    void api
      .listTopics(selectedSubjectId)
      .then((items) => {
        if (request !== topicRequest.current) return;
        setTopics(items);
      })
      .catch((reason: unknown) => {
        if (request === topicRequest.current) setError(errorMessage(reason));
      })
      .finally(() => {
        if (request === topicRequest.current) setLoadingTopics(false);
      });
  }, [academicRevision, selectedSubjectId]);

  useEffect(() => {
    const request = ++contextGeneration.current;
    generationRequest.current += 1;
    queueMicrotask(() => {
      if (request !== contextGeneration.current) return;
      setQuestions([]);
      setLoadedTopicId("");
      setQuestionId("");
      setAttempts([]);
      setMastery(null);
      setQuestionForm(emptyQuestion);
      setAttemptForm(emptyAttempt);
      setSubmittingQuestion(false);
      setSubmittingAttempt(false);
      setGeneratedCandidates([]);
      setGenerationError("");
      setGenerating(false);
      setSuccess("");
      setError("");
      setLoadingPractice(Boolean(selectedTopicId));
    });

    if (!selectedTopicId) return;
    const topicId = selectedTopicId;
    void Promise.all([api.listQuestions(topicId), api.getMastery(topicId)])
      .then(([nextQuestions, nextMastery]) => {
        if (!isActiveTopic(topicId, request)) return;
        setQuestions(nextQuestions);
        setMastery(nextMastery);
        setLoadedTopicId(topicId);
        setQuestionId(nextQuestions[0]?.id ?? "");
      })
      .catch((reason: unknown) => {
        if (isActiveTopic(topicId, request)) setError(errorMessage(reason));
      })
      .finally(() => {
        if (isActiveTopic(topicId, request)) setLoadingPractice(false);
      });
  }, [selectedTopicId]);

  useEffect(() => {
    const requestedQuestionId = questionId;
    const requestedRevision = attemptHistoryRevision.current;
    queueMicrotask(() => {
      if (activeQuestionId.current !== requestedQuestionId) return;
      setAttempts([]);
      setAttemptForm(emptyAttempt);
      setSuccess("");
    });
    if (!questionId) return;
    let ignore = false;
    void api
      .listAttempts(requestedQuestionId)
      .then((items) => {
        if (
          !ignore &&
          activeQuestionId.current === requestedQuestionId &&
          attemptHistoryRevision.current === requestedRevision
        ) setAttempts(items);
      })
      .catch((reason: unknown) => {
        if (!ignore && activeQuestionId.current === requestedQuestionId) {
          setError(errorMessage(reason));
        }
      });
    return () => {
      ignore = true;
    };
  }, [questionId]);

  function isActiveTopic(topicId: string, generation: number): boolean {
    return activeTopicId.current === topicId && contextGeneration.current === generation;
  }

  async function createQuestion(event: FormEvent) {
    event.preventDefault();
    if (!selectedTopicId || submittingQuestion) return;
    const topicId = selectedTopicId;
    const generation = contextGeneration.current;
    const form = questionForm;
    setSubmittingQuestion(true);
    setError("");
    setSuccess("");
    try {
      const created = await api.createQuestion(topicId, {
        prompt: form.prompt,
        answer_reference: form.answerReference,
        difficulty: form.difficulty,
      });
      if (!isActiveTopic(topicId, generation)) return;
      setQuestions((items) => [...items, created]);
      setQuestionId(created.id);
      setQuestionForm(emptyQuestion);
      setSuccess("Question saved.");
    } catch (reason) {
      if (isActiveTopic(topicId, generation)) setError(errorMessage(reason));
    } finally {
      if (isActiveTopic(topicId, generation)) setSubmittingQuestion(false);
    }
  }

  async function generateQuestions() {
    if (!selectedTopicId || generating) return;
    const topicId = selectedTopicId;
    const context = contextGeneration.current;
    const request = ++generationRequest.current;
    setGenerating(true);
    setGenerationError("");
    try {
      const result = await api.generateQuestions(topicId, {
        count: Number(generationCount),
        difficulty: generationDifficulty,
      });
      if (
        request !== generationRequest.current ||
        !isActiveTopic(topicId, context) ||
        result.topic_id !== topicId
      ) return;
      setGeneratedCandidates(result.candidates);
    } catch (reason) {
      if (request === generationRequest.current && isActiveTopic(topicId, context)) {
        setGenerationError(errorMessage(reason));
      }
    } finally {
      if (request === generationRequest.current && isActiveTopic(topicId, context)) {
        setGenerating(false);
      }
    }
  }

  function chooseCandidate(candidate: QuestionGenerationCandidate) {
    setQuestionForm({
      prompt: candidate.prompt,
      answerReference: candidate.answer_reference,
      difficulty: candidate.difficulty,
    });
    setSuccess("Candidate copied. Review it before saving.");
  }

  function chooseQuestion(id: string) {
    activeQuestionId.current = id;
    setQuestionId(id);
    setAttempts([]);
    setAttemptForm(emptyAttempt);
    setSubmittingAttempt(false);
    setSuccess("");
    setError("");
  }

  async function editQuestion(question: Question) {
    const prompt = window.prompt("Question prompt", question.prompt)?.trim();
    if (!prompt) return;
    const answerReference = window
      .prompt("Answer reference", question.answer_reference)
      ?.trim();
    if (!answerReference) return;
    const difficulty = window.prompt("Difficulty: easy, medium, or hard", question.difficulty)?.trim();
    if (!difficulty) return;
    if (!["easy", "medium", "hard"].includes(difficulty)) {
      setError("Difficulty must be easy, medium, or hard");
      return;
    }
    const topicId = question.topic_id;
    const generation = contextGeneration.current;
    setError("");
    try {
      const saved = await api.updateQuestion(question.id, {
        prompt,
        answer_reference: answerReference,
        difficulty: difficulty as QuestionDifficulty,
      });
      if (!isActiveTopic(topicId, generation)) return;
      setQuestions((items) => replace(items, saved));
      setSuccess("Question updated.");
    } catch (reason) {
      if (isActiveTopic(topicId, generation)) setError(errorMessage(reason));
    }
  }

  async function deleteQuestion(question: Question) {
    if (!window.confirm("Delete this question?")) return;
    const topicId = question.topic_id;
    const generation = contextGeneration.current;
    setError("");
    try {
      await api.deleteQuestion(question.id);
      if (!isActiveTopic(topicId, generation)) return;
      setQuestions((items) => {
        const remaining = items.filter((item) => item.id !== question.id);
        setQuestionId((current) => current === question.id ? (remaining[0]?.id ?? "") : current);
        return remaining;
      });
      setSuccess("Question deleted.");
    } catch (reason) {
      if (isActiveTopic(topicId, generation)) setError(errorMessage(reason));
    }
  }

  async function recordAttempt(event: FormEvent) {
    event.preventDefault();
    if (!selectedTopicId || !questionId || submittingAttempt) return;
    const topicId = selectedTopicId;
    const requestedQuestionId = questionId;
    const generation = contextGeneration.current;
    const form = attemptForm;
    setSubmittingAttempt(true);
    setError("");
    setSuccess("");
    try {
      const result = await api.recordAttempt(requestedQuestionId, {
        correct: form.correct === "true",
        hints_used: Number(form.hintsUsed),
        solution_seen: form.solutionSeen,
        time_spent_seconds: Number(form.timeSpentSeconds),
      });
      onAttemptRecorded?.();
      if (!isActiveTopic(topicId, generation)) return;
      setMastery(result.mastery);
      if (activeQuestionId.current !== requestedQuestionId) return;
      attemptHistoryRevision.current += 1;
      setAttempts((items) => [result.attempt, ...items]);
      setAttemptForm(emptyAttempt);
      setSuccess(`Attempt recorded. Mastery updated to ${result.mastery.score}.`);
    } catch (reason) {
      if (
        isActiveTopic(topicId, generation) &&
        activeQuestionId.current === requestedQuestionId
      ) setError(errorMessage(reason));
    } finally {
      if (
        isActiveTopic(topicId, generation) &&
        activeQuestionId.current === requestedQuestionId
      ) setSubmittingAttempt(false);
    }
  }

  return (
    <section className="panel space-y-5" aria-labelledby="practice-heading">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Practice evidence</p>
          <h2 id="practice-heading">Questions and mastery</h2>
          <p className="selected-context" aria-live="polite">
            {selectedTopic
              ? `${selectedSubject?.name ?? "Subject"} / ${selectedTopic.name}`
              : "Choose a Topic or use a Global Plan recommendation."}
          </p>
        </div>
        <div className="mastery-score" aria-label="Current mastery">
          {visibleMastery ? <>
            <strong>{visibleMastery.score}</strong>
            <span>/ 100 mastery</span>
          </> : <span>No mastery loaded</span>}
        </div>
      </div>

      {error && <p role="alert" className="error-banner">{error}</p>}
      {success && <p role="status" className="success-banner">{success}</p>}

      <div className="practice-selectors">
        <label><span>Subject</span><select aria-label="Practice subject" value={selectedSubjectId} disabled={loadingSubjects} onChange={(event) => onSubjectSelected(event.target.value)}>
          <option value="">Choose a subject</option>
          {subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}
        </select></label>
        <label><span>Topic</span><select aria-label="Practice topic" value={selectedTopicId} disabled={!selectedSubjectId || loadingTopics} onChange={(event) => onTopicSelected(selectedSubjectId, event.target.value)}>
          <option value="">Choose a topic</option>
          {topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}
        </select></label>
      </div>

      {!loadingSubjects && subjects.length === 0 && <p className="empty">Create your first Subject in Academic setup to begin.</p>}
      {selectedSubjectId && !loadingTopics && topics.length === 0 && <p className="empty">Add a Topic in Academic setup to begin practicing.</p>}
      {loadingPractice && <p className="empty">Loading Questions and Mastery…</p>}
      {visibleMastery?.updated_at === null && <p className="empty">No attempts yet. Mastery starts at 0.00.</p>}

      {selectedTopicId && <div className="space-y-3" aria-label="Generate practice">
        <div>
          <h3>Generate Practice</h3>
          <p className="empty">Optional AI previews are not saved. Review generated answers before using them.</p>
        </div>
        <div className="practice-selectors generation-controls">
          <label><span>Candidate count</span><select aria-label="Generation count" value={generationCount} onChange={(event) => setGenerationCount(event.target.value)}>
            {Array.from({ length: 10 }, (_, index) => index + 1).map((value) => <option key={value} value={value}>{value}</option>)}
          </select></label>
          <label><span>Difficulty</span><select aria-label="Generation difficulty" value={generationDifficulty} onChange={(event) => setGenerationDifficulty(event.target.value as GenerationDifficulty)}>
            <option value="mixed">Mixed</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
          </select></label>
          <button type="button" disabled={generating} onClick={() => void generateQuestions()}>{generating ? "Generating…" : generationError ? "Retry" : "Generate"}</button>
        </div>
        {generationError && <div><p role="alert" className="error-banner">{generationError}</p><p className="empty">AI is optional. You can still create a Question manually.</p></div>}
        {generatedCandidates.length > 0 && <ul className="item-list" aria-label="Generated candidates">
          {generatedCandidates.map((candidate, index) => <li key={index}><div className="item-main"><strong>{candidate.prompt}</strong><p className="whitespace-pre-wrap">{candidate.answer_reference}</p><span>{candidate.difficulty}</span>{candidate.duplicate_existing && <span className="error-banner">Possible duplicate of an existing Question</span>}</div><button type="button" onClick={() => chooseCandidate(candidate)}>Use candidate</button></li>)}
        </ul>}
      </div>}

      {selectedTopicId && <div>
        <h3>Review and save question</h3>
        <form className="question-form" onSubmit={createQuestion}>
          <label><span>Question prompt</span><textarea aria-label="Question prompt" required value={questionForm.prompt} onChange={(event) => setQuestionForm({ ...questionForm, prompt: event.target.value })} /></label>
          <label><span>Answer reference</span><textarea aria-label="Answer reference" required value={questionForm.answerReference} onChange={(event) => setQuestionForm({ ...questionForm, answerReference: event.target.value })} /></label>
          <label><span>Difficulty</span><select aria-label="Question difficulty" value={questionForm.difficulty} onChange={(event) => setQuestionForm({ ...questionForm, difficulty: event.target.value as QuestionDifficulty })}><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select></label>
          <button type="submit" disabled={submittingQuestion}>{submittingQuestion ? "Saving…" : "Add question"}</button>
        </form>
      </div>}

      <div className="practice-grid">
        <div>
          <h3>Questions</h3>
          {!selectedTopicId ? <p className="empty">Choose a Topic or use a Global Plan recommendation.</p> : !loadingPractice && !visibleQuestions.length ? <p className="empty">Create a Question manually, or generate an optional AI preview.</p> : <ul className="item-list">{visibleQuestions.map((question) => <li key={question.id} className={question.id === questionId ? "selected" : ""}><button type="button" aria-pressed={question.id === questionId} className="item-main" onClick={() => chooseQuestion(question.id)}><strong>{question.prompt}</strong><span>{question.difficulty}</span></button><button className="quiet" onClick={() => void editQuestion(question)}>Edit</button><button className="danger" onClick={() => void deleteQuestion(question)}>Delete</button></li>)}</ul>}
        </div>

        <div>
          <h3>Attempt</h3>
          {!selectedQuestion ? <p className="empty">Select a Question to practice.</p> : <>
            <div className="question-detail"><strong>{selectedQuestion.prompt}</strong><details className="answer-reference"><summary>Show answer reference</summary><p>{selectedQuestion.answer_reference}</p></details></div>
            <TutorPanel questionId={selectedQuestion.id} />
            <p className="empty">Tutor help is not recorded automatically. Report hints and solution use yourself.</p>
            <form className="attempt-form" onSubmit={recordAttempt}>
              <label><span>Result</span><select aria-label="Attempt correctness" value={attemptForm.correct} onChange={(event) => setAttemptForm({ ...attemptForm, correct: event.target.value })}><option value="true">Correct</option><option value="false">Incorrect</option></select></label>
              <label><span>Hints used</span><select aria-label="Hints used" value={attemptForm.hintsUsed} onChange={(event) => setAttemptForm({ ...attemptForm, hintsUsed: event.target.value })}>{[0, 1, 2, 3].map((value) => <option key={value} value={value}>{value} hints</option>)}</select></label>
              <label><span>Time spent (seconds)</span><input aria-label="Time spent seconds" required type="number" min="0" value={attemptForm.timeSpentSeconds} onChange={(event) => setAttemptForm({ ...attemptForm, timeSpentSeconds: event.target.value })} /></label>
              <label className="checkbox"><input aria-label="Solution seen" type="checkbox" checked={attemptForm.solutionSeen} onChange={(event) => setAttemptForm({ ...attemptForm, solutionSeen: event.target.checked })} /> Solution seen</label>
              <button type="submit" disabled={submittingAttempt}>{submittingAttempt ? "Recording…" : "Record attempt"}</button>
            </form>
          </>}
        </div>
      </div>

      {selectedQuestion && <div><h3>Recent evidence</h3>{!attempts.length ? <p className="empty">No attempts yet. Record your first self-reported Attempt when you finish.</p> : <ul className="attempt-history">{attempts.map((attempt) => <li key={attempt.id}><strong>{attempt.correct ? "Correct" : "Incorrect"}</strong><span>{attempt.hints_used} hints · {attempt.solution_seen ? "solution seen" : "solution hidden"} · {attempt.time_spent_seconds}s</span></li>)}</ul>}</div>}
    </section>
  );
}

function replace<T extends { id: string }>(items: T[], saved: T): T[] {
  return items.map((item) => item.id === saved.id ? saved : item);
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "Something went wrong";
}
