"use client";

import { FormEvent, useEffect, useState } from "react";

import { api } from "../lib/api";
import type { Exam, ExamTopic, Subject, Topic } from "../lib/types";

type FormState = { name: string; description: string };
const emptyForm: FormState = { name: "", description: "" };

type DomainManagerProps = {
  onPlannerInputsChanged?: () => void;
};

export function DomainManager({ onPlannerInputsChanged }: DomainManagerProps = {}) {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState("");
  const [topics, setTopics] = useState<Topic[]>([]);
  const [exams, setExams] = useState<Exam[]>([]);
  const [selectedExamId, setSelectedExamId] = useState("");
  const [assignments, setAssignments] = useState<ExamTopic[]>([]);
  const [subjectForm, setSubjectForm] = useState<FormState>(emptyForm);
  const [topicForm, setTopicForm] = useState<FormState>(emptyForm);
  const [examForm, setExamForm] = useState({ ...emptyForm, examDate: "" });
  const [assignment, setAssignment] = useState({ topicId: "", weight: "1" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const selectedSubject = subjects.find((item) => item.id === selectedSubjectId);
  const selectedExam = exams.find((item) => item.id === selectedExamId);

  useEffect(() => {
    void api
      .listSubjects()
      .then((items) => {
        setSubjects(items);
        setSelectedSubjectId((current) => current || items[0]?.id || "");
      })
      .catch((reason: unknown) => setError(errorMessage(reason)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedSubjectId) {
      return;
    }
    let ignore = false;
    void Promise.all([api.listTopics(selectedSubjectId), api.listExams(selectedSubjectId)])
      .then(([nextTopics, nextExams]) => {
        if (ignore) return;
        setTopics(nextTopics);
        setExams(nextExams);
        setSelectedExamId((current) =>
          nextExams.some((exam) => exam.id === current) ? current : nextExams[0]?.id || "",
        );
        if (!nextExams.length) setAssignments([]);
      })
      .catch((reason: unknown) => setError(errorMessage(reason)));
    return () => { ignore = true; };
  }, [selectedSubjectId]);

  useEffect(() => {
    if (!selectedExamId) {
      return;
    }
    let ignore = false;
    void api
      .listExamTopics(selectedExamId)
      .then((items) => { if (!ignore) setAssignments(items); })
      .catch((reason: unknown) => setError(errorMessage(reason)));
    return () => { ignore = true; };
  }, [selectedExamId]);

  async function createSubject(event: FormEvent) {
    event.preventDefault();
    await act(async () => {
      const created = await api.createSubject(subjectForm);
      setSubjects((items) => [...items, created]);
      chooseSubject(created.id);
      setSubjectForm(emptyForm);
    });
  }

  async function createTopic(event: FormEvent) {
    event.preventDefault();
    await act(async () => {
      const created = await api.createTopic(selectedSubjectId, topicForm);
      setTopics((items) => [...items, created]);
      setTopicForm(emptyForm);
    });
  }

  async function createExam(event: FormEvent) {
    event.preventDefault();
    await act(async () => {
      const created = await api.createExam(selectedSubjectId, {
        name: examForm.name,
        description: examForm.description,
        exam_date: new Date(examForm.examDate).toISOString(),
      });
      setExams((items) => [...items, created]);
      setSelectedExamId(created.id);
      setExamForm({ ...emptyForm, examDate: "" });
      onPlannerInputsChanged?.();
    });
  }

  async function assignTopic(event: FormEvent) {
    event.preventDefault();
    await act(async () => {
      const saved = await api.putExamTopic(
        selectedExamId,
        assignment.topicId,
        Number(assignment.weight),
      );
      setAssignments((items) => [...items.filter((item) => item.topic_id !== saved.topic_id), saved]);
      onPlannerInputsChanged?.();
    });
  }

  async function rename(kind: "subject" | "topic" | "exam", id: string, current: string) {
    const name = window.prompt("New name", current)?.trim();
    if (!name || name === current) return;
    await act(async () => {
      if (kind === "subject") {
        const saved = await api.updateSubject(id, { name });
        setSubjects((items) => replace(items, saved));
      } else if (kind === "topic") {
        const saved = await api.updateTopic(id, { name });
        setTopics((items) => replace(items, saved));
      } else {
        const saved = await api.updateExam(id, { name });
        setExams((items) => replace(items, saved));
      }
      onPlannerInputsChanged?.();
    });
  }

  async function remove(kind: "subject" | "topic" | "exam", id: string) {
    if (!window.confirm("Delete this item?")) return;
    await act(async () => {
      if (kind === "subject") {
        await api.deleteSubject(id);
        setSubjects((items) => items.filter((item) => item.id !== id));
        if (selectedSubjectId === id) setSelectedSubjectId("");
      } else if (kind === "topic") {
        await api.deleteTopic(id);
        setTopics((items) => items.filter((item) => item.id !== id));
      } else {
        await api.deleteExam(id);
        setExams((items) => items.filter((item) => item.id !== id));
        if (selectedExamId === id) setSelectedExamId("");
        onPlannerInputsChanged?.();
      }
    });
  }

  async function removeAssignment(topicId: string) {
    await act(async () => {
      await api.deleteExamTopic(selectedExamId, topicId);
      setAssignments((items) => items.filter((item) => item.topic_id !== topicId));
      onPlannerInputsChanged?.();
    });
  }

  function chooseSubject(id: string) {
    setSelectedSubjectId(id);
    setTopics([]);
    setExams([]);
    setSelectedExamId("");
    setAssignments([]);
  }

  function chooseExam(id: string) {
    setSelectedExamId(id);
    setAssignments([]);
  }

  async function act(action: () => Promise<void>) {
    setError("");
    try {
      await action();
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  if (loading) return <p className="panel">Loading subjects…</p>;

  return (
    <div className="space-y-6">
      {error && <p role="alert" className="error-banner">{error}</p>}

      <section className="panel">
        <div className="section-heading">
          <div><p className="eyebrow">Subjects</p><h2>Your courses</h2></div>
        </div>
        <form className="form-grid" onSubmit={createSubject}>
          <input aria-label="Subject name" required placeholder="Subject name" value={subjectForm.name} onChange={(event) => setSubjectForm({ ...subjectForm, name: event.target.value })} />
          <input aria-label="Subject description" placeholder="Description (optional)" value={subjectForm.description} onChange={(event) => setSubjectForm({ ...subjectForm, description: event.target.value })} />
          <button type="submit">Add subject</button>
        </form>
        {subjects.length === 0 ? <p className="empty">Create your first subject to begin.</p> : (
          <ul className="item-list">{subjects.map((subject) => (
            <li key={subject.id} className={subject.id === selectedSubjectId ? "selected" : ""}>
              <button className="item-main" onClick={() => chooseSubject(subject.id)}><strong>{subject.name}</strong><span>{subject.description || "No description"}</span></button>
              <button className="quiet" onClick={() => void rename("subject", subject.id, subject.name)}>Rename</button>
              <button className="danger" onClick={() => void remove("subject", subject.id)}>Delete</button>
            </li>
          ))}</ul>
        )}
      </section>

      {selectedSubject && <div className="domain-grid">
        <section className="panel">
          <p className="eyebrow">{selectedSubject.name}</p><h2>Topics</h2>
          <form className="form-grid" onSubmit={createTopic}>
            <input aria-label="Topic name" required placeholder="Topic name" value={topicForm.name} onChange={(event) => setTopicForm({ ...topicForm, name: event.target.value })} />
            <input aria-label="Topic description" placeholder="Description (optional)" value={topicForm.description} onChange={(event) => setTopicForm({ ...topicForm, description: event.target.value })} />
            <button type="submit">Add topic</button>
          </form>
          <EntityList items={topics} onRename={(item) => rename("topic", item.id, item.name)} onDelete={(item) => remove("topic", item.id)} />
        </section>

        <section className="panel">
          <p className="eyebrow">{selectedSubject.name}</p><h2>Exams</h2>
          <form className="form-grid" onSubmit={createExam}>
            <input aria-label="Exam name" required placeholder="Exam name" value={examForm.name} onChange={(event) => setExamForm({ ...examForm, name: event.target.value })} />
            <input aria-label="Exam date" required type="datetime-local" value={examForm.examDate} onChange={(event) => setExamForm({ ...examForm, examDate: event.target.value })} />
            <input aria-label="Exam description" placeholder="Description (optional)" value={examForm.description} onChange={(event) => setExamForm({ ...examForm, description: event.target.value })} />
            <button type="submit">Add exam</button>
          </form>
          <ul className="item-list">{exams.map((exam) => (
            <li key={exam.id} className={exam.id === selectedExamId ? "selected" : ""}>
              <button className="item-main" onClick={() => chooseExam(exam.id)}><strong>{exam.name}</strong><span>{new Date(exam.exam_date).toLocaleString()}</span></button>
              <button className="quiet" onClick={() => void rename("exam", exam.id, exam.name)}>Rename</button>
              <button className="danger" onClick={() => void remove("exam", exam.id)}>Delete</button>
            </li>
          ))}</ul>
        </section>
      </div>}

      {selectedExam && <section className="panel">
        <p className="eyebrow">{selectedExam.name}</p><h2>Weighted topics</h2>
        <form className="assignment-form" onSubmit={assignTopic}>
          <select aria-label="Topic to assign" required value={assignment.topicId} onChange={(event) => setAssignment({ ...assignment, topicId: event.target.value })}>
            <option value="">Choose a topic</option>{topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}
          </select>
          <input aria-label="Topic weight" required type="number" min="0.01" max="1" step="0.01" value={assignment.weight} onChange={(event) => setAssignment({ ...assignment, weight: event.target.value })} />
          <button type="submit">Save weight</button>
        </form>
        <ul className="item-list">{assignments.map((item) => (
          <li key={item.topic_id}><div className="item-main"><strong>{topics.find((topic) => topic.id === item.topic_id)?.name ?? "Topic"}</strong><span>Weight {item.weight}</span></div><button className="danger" onClick={() => void removeAssignment(item.topic_id)}>Remove</button></li>
        ))}</ul>
      </section>}
    </div>
  );
}

function EntityList<T extends { id: string; name: string; description: string | null }>({ items, onRename, onDelete }: { items: T[]; onRename: (item: T) => Promise<void>; onDelete: (item: T) => Promise<void> }) {
  if (!items.length) return <p className="empty">Nothing here yet.</p>;
  return <ul className="item-list">{items.map((item) => <li key={item.id}><div className="item-main"><strong>{item.name}</strong><span>{item.description || "No description"}</span></div><button className="quiet" onClick={() => void onRename(item)}>Rename</button><button className="danger" onClick={() => void onDelete(item)}>Delete</button></li>)}</ul>;
}

function replace<T extends { id: string }>(items: T[], saved: T): T[] {
  return items.map((item) => item.id === saved.id ? saved : item);
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "Something went wrong";
}
