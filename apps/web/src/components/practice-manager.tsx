"use client";

import { FormEvent, useEffect, useState } from "react";

import { api } from "../lib/api";
import type {
  Attempt,
  Mastery,
  Question,
  QuestionDifficulty,
  Subject,
  Topic,
} from "../lib/types";

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

export function PracticeManager() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [subjectId, setSubjectId] = useState("");
  const [topics, setTopics] = useState<Topic[]>([]);
  const [topicId, setTopicId] = useState("");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [questionId, setQuestionId] = useState("");
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [mastery, setMastery] = useState<Mastery | null>(null);
  const [questionForm, setQuestionForm] = useState(emptyQuestion);
  const [attemptForm, setAttemptForm] = useState(emptyAttempt);
  const [submittingAttempt, setSubmittingAttempt] = useState(false);
  const [error, setError] = useState("");

  const selectedQuestion = questions.find((item) => item.id === questionId);

  useEffect(() => {
    void api
      .listSubjects()
      .then((items) => {
        setSubjects(items);
        setSubjectId(items[0]?.id ?? "");
      })
      .catch((reason: unknown) => setError(errorMessage(reason)));
  }, []);

  useEffect(() => {
    if (!subjectId) return;
    let ignore = false;
    void api
      .listTopics(subjectId)
      .then((items) => {
        if (ignore) return;
        setTopics(items);
        setTopicId((current) =>
          items.some((topic) => topic.id === current) ? current : (items[0]?.id ?? ""),
        );
      })
      .catch((reason: unknown) => setError(errorMessage(reason)));
    return () => {
      ignore = true;
    };
  }, [subjectId]);

  useEffect(() => {
    if (!topicId) return;
    let ignore = false;
    void Promise.all([api.listQuestions(topicId), api.getMastery(topicId)])
      .then(([nextQuestions, nextMastery]) => {
        if (ignore) return;
        setQuestions(nextQuestions);
        setMastery(nextMastery);
        setQuestionId((current) =>
          nextQuestions.some((question) => question.id === current)
            ? current
            : (nextQuestions[0]?.id ?? ""),
        );
      })
      .catch((reason: unknown) => setError(errorMessage(reason)));
    return () => {
      ignore = true;
    };
  }, [topicId]);

  useEffect(() => {
    if (!questionId) return;
    let ignore = false;
    void api
      .listAttempts(questionId)
      .then((items) => {
        if (!ignore) setAttempts(items);
      })
      .catch((reason: unknown) => setError(errorMessage(reason)));
    return () => {
      ignore = true;
    };
  }, [questionId]);

  async function createQuestion(event: FormEvent) {
    event.preventDefault();
    await act(async () => {
      const created = await api.createQuestion(topicId, {
        prompt: questionForm.prompt,
        answer_reference: questionForm.answerReference,
        difficulty: questionForm.difficulty,
      });
      setQuestions((items) => [...items, created]);
      setQuestionId(created.id);
      setQuestionForm(emptyQuestion);
    });
  }

  function chooseSubject(id: string) {
    setSubjectId(id);
    setTopics([]);
    setTopicId("");
    setQuestions([]);
    setQuestionId("");
    setAttempts([]);
    setMastery(null);
  }

  function chooseTopic(id: string) {
    setTopicId(id);
    setQuestions([]);
    setQuestionId("");
    setAttempts([]);
    setMastery(null);
  }

  function chooseQuestion(id: string) {
    setQuestionId(id);
    setAttempts([]);
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
    await act(async () => {
      const saved = await api.updateQuestion(question.id, {
        prompt,
        answer_reference: answerReference,
        difficulty: difficulty as QuestionDifficulty,
      });
      setQuestions((items) => replace(items, saved));
    });
  }

  async function deleteQuestion(question: Question) {
    if (!window.confirm("Delete this question?")) return;
    await act(async () => {
      await api.deleteQuestion(question.id);
      const remaining = questions.filter((item) => item.id !== question.id);
      setQuestions(remaining);
      if (questionId === question.id) setQuestionId(remaining[0]?.id ?? "");
    });
  }

  async function recordAttempt(event: FormEvent) {
    event.preventDefault();
    if (submittingAttempt) return;
    setSubmittingAttempt(true);
    await act(async () => {
      const result = await api.recordAttempt(questionId, {
        correct: attemptForm.correct === "true",
        hints_used: Number(attemptForm.hintsUsed),
        solution_seen: attemptForm.solutionSeen,
        time_spent_seconds: Number(attemptForm.timeSpentSeconds),
      });
      setMastery(result.mastery);
      setAttempts((items) => [result.attempt, ...items]);
      setAttemptForm(emptyAttempt);
    });
    setSubmittingAttempt(false);
  }

  async function act(action: () => Promise<void>) {
    setError("");
    try {
      await action();
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  return (
    <section className="panel space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Practice evidence</p>
          <h2>Questions and mastery</h2>
        </div>
        <div className="mastery-score" aria-label="Current mastery">
          <strong>{mastery?.score ?? "0.00"}</strong>
          <span>/ 100 mastery</span>
        </div>
      </div>
      {error && <p role="alert" className="error-banner">{error}</p>}

      <div className="practice-selectors">
        <select aria-label="Practice subject" value={subjectId} onChange={(event) => chooseSubject(event.target.value)}>
          <option value="">Choose a subject</option>
          {subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}
        </select>
        <select aria-label="Practice topic" value={topicId} onChange={(event) => chooseTopic(event.target.value)}>
          <option value="">Choose a topic</option>
          {topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}
        </select>
      </div>

      {topicId && <form className="question-form" onSubmit={createQuestion}>
        <textarea aria-label="Question prompt" required placeholder="Question prompt" value={questionForm.prompt} onChange={(event) => setQuestionForm({ ...questionForm, prompt: event.target.value })} />
        <textarea aria-label="Answer reference" required placeholder="Answer reference" value={questionForm.answerReference} onChange={(event) => setQuestionForm({ ...questionForm, answerReference: event.target.value })} />
        <select aria-label="Question difficulty" value={questionForm.difficulty} onChange={(event) => setQuestionForm({ ...questionForm, difficulty: event.target.value as QuestionDifficulty })}>
          <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
        </select>
        <button type="submit">Add question</button>
      </form>}

      <div className="practice-grid">
        <div>
          <h3>Questions</h3>
          {!questions.length ? <p className="empty">No questions for this topic yet.</p> : <ul className="item-list">{questions.map((question) => (
            <li key={question.id} className={question.id === questionId ? "selected" : ""}>
              <button className="item-main" onClick={() => chooseQuestion(question.id)}><strong>{question.prompt}</strong><span>{question.difficulty}</span></button>
              <button className="quiet" onClick={() => void editQuestion(question)}>Edit</button>
              <button className="danger" onClick={() => void deleteQuestion(question)}>Delete</button>
            </li>
          ))}</ul>}
        </div>

        <div>
          <h3>Attempt</h3>
          {!selectedQuestion ? <p className="empty">Select a question to practice.</p> : <>
            <div className="question-detail"><strong>{selectedQuestion.prompt}</strong><p>Answer reference: {selectedQuestion.answer_reference}</p></div>
            <form className="attempt-form" onSubmit={recordAttempt}>
              <select aria-label="Attempt correctness" value={attemptForm.correct} onChange={(event) => setAttemptForm({ ...attemptForm, correct: event.target.value })}>
                <option value="true">Correct</option><option value="false">Incorrect</option>
              </select>
              <select aria-label="Hints used" value={attemptForm.hintsUsed} onChange={(event) => setAttemptForm({ ...attemptForm, hintsUsed: event.target.value })}>
                {[0, 1, 2, 3].map((value) => <option key={value} value={value}>{value} hints</option>)}
              </select>
              <input aria-label="Time spent seconds" required type="number" min="0" value={attemptForm.timeSpentSeconds} onChange={(event) => setAttemptForm({ ...attemptForm, timeSpentSeconds: event.target.value })} />
              <label className="checkbox"><input type="checkbox" checked={attemptForm.solutionSeen} onChange={(event) => setAttemptForm({ ...attemptForm, solutionSeen: event.target.checked })} /> Solution seen</label>
              <button type="submit" disabled={submittingAttempt}>{submittingAttempt ? "Recording…" : "Record attempt"}</button>
            </form>
          </>}
        </div>
      </div>

      {selectedQuestion && <div><h3>Recent evidence</h3>{!attempts.length ? <p className="empty">No attempts yet.</p> : <ul className="attempt-history">{attempts.map((attempt) => <li key={attempt.id}><strong>{attempt.correct ? "Correct" : "Incorrect"}</strong><span>{attempt.hints_used} hints · {attempt.solution_seen ? "solution seen" : "solution hidden"} · {attempt.time_spent_seconds}s</span></li>)}</ul>}</div>}
    </section>
  );
}

function replace<T extends { id: string }>(items: T[], saved: T): T[] {
  return items.map((item) => item.id === saved.id ? saved : item);
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "Something went wrong";
}
