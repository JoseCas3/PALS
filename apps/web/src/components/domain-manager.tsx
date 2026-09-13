"use client";

import { FormEvent, useEffect, useLayoutEffect, useRef, useState } from "react";

import { api } from "../lib/api";
import type { Exam, ExamTopic, Subject, Topic } from "../lib/types";

type FormState = { name: string; description: string };
const emptyForm: FormState = { name: "", description: "" };

type DomainManagerProps = {
  selectedSubjectId: string;
  selectedTopicId: string;
  onSubjectSelected: (subjectId: string) => void;
  onTopicSelected: (subjectId: string, topicId: string) => void;
  onAcademicDataChanged?: () => void;
  onPlannerInputsChanged?: () => void;
};

export function DomainManager({
  selectedSubjectId,
  selectedTopicId,
  onSubjectSelected,
  onTopicSelected,
  onAcademicDataChanged,
  onPlannerInputsChanged,
}: DomainManagerProps) {
  const [subjects, setSubjects] = useState<Subject[]>([]);
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
  const activeSubjectId = useRef(selectedSubjectId);
  const activeTopicId = useRef(selectedTopicId);
  const activeExamId = useRef(selectedExamId);
  useLayoutEffect(() => {
    activeSubjectId.current = selectedSubjectId;
  }, [selectedSubjectId]);
  useLayoutEffect(() => {
    activeTopicId.current = selectedTopicId;
  }, [selectedTopicId]);
  useLayoutEffect(() => {
    activeExamId.current = selectedExamId;
  }, [selectedExamId]);

  const selectedSubject = subjects.find((item) => item.id === selectedSubjectId);
  const selectedExam = exams.find((item) => item.id === selectedExamId);

  useEffect(() => {
    void api
      .listSubjects()
      .then((items) => {
        setSubjects(items);
        if (!activeSubjectId.current && items[0]) onSubjectSelected(items[0].id);
      })
      .catch((reason: unknown) => setError(errorMessage(reason)))
      .finally(() => setLoading(false));
  }, [onSubjectSelected]);

  useEffect(() => {
    queueMicrotask(() => {
      setTopics([]);
      setExams([]);
      setSelectedExamId("");
      setAssignments([]);
    });
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
      .catch((reason: unknown) => { if (!ignore) setError(errorMessage(reason)); });
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
      .catch((reason: unknown) => { if (!ignore) setError(errorMessage(reason)); });
    return () => { ignore = true; };
  }, [selectedExamId]);

  async function createSubject(event: FormEvent) {
    event.preventDefault();
    const subjectId = selectedSubjectId;
    const form = subjectForm;
    await act(async () => {
      const created = await api.createSubject(form);
      setSubjects((items) => [...items, created]);
      onAcademicDataChanged?.();
      if (activeSubjectId.current !== subjectId) return;
      chooseSubject(created.id);
      setSubjectForm(emptyForm);
    }, () => activeSubjectId.current === subjectId);
  }

  async function createTopic(event: FormEvent) {
    event.preventDefault();
    const subjectId = selectedSubjectId;
    const topicId = selectedTopicId;
    const form = topicForm;
    await act(async () => {
      const created = await api.createTopic(subjectId, form);
      onAcademicDataChanged?.();
      if (
        activeSubjectId.current !== subjectId ||
        activeTopicId.current !== topicId
      ) return;
      setTopics((items) => [...items, created]);
      onTopicSelected(subjectId, created.id);
      setTopicForm(emptyForm);
    }, () => activeSubjectId.current === subjectId && activeTopicId.current === topicId);
  }

  async function createExam(event: FormEvent) {
    event.preventDefault();
    const subjectId = selectedSubjectId;
    const examId = selectedExamId;
    const form = examForm;
    await act(async () => {
      const created = await api.createExam(subjectId, {
        name: form.name,
        description: form.description,
        exam_date: new Date(form.examDate).toISOString(),
      });
      onAcademicDataChanged?.();
      onPlannerInputsChanged?.();
      if (!isActiveExam(subjectId, examId)) return;
      setExams((items) => [...items, created]);
      activeExamId.current = created.id;
      setSelectedExamId(created.id);
      setExamForm({ ...emptyForm, examDate: "" });
    }, () => isActiveExam(subjectId, examId));
  }

  async function assignTopic(event: FormEvent) {
    event.preventDefault();
    const subjectId = selectedSubjectId;
    const examId = selectedExamId;
    const submittedAssignment = assignment;
    await act(async () => {
      const saved = await api.putExamTopic(
        examId,
        submittedAssignment.topicId,
        Number(submittedAssignment.weight),
      );
      onPlannerInputsChanged?.();
      if (!isActiveExam(subjectId, examId)) return;
      setAssignments((items) => [...items.filter((item) => item.topic_id !== saved.topic_id), saved]);
    }, () => isActiveExam(subjectId, examId));
  }

  async function rename(kind: "subject" | "topic" | "exam", id: string, current: string) {
    const name = window.prompt("New name", current)?.trim();
    if (!name || name === current) return;
    const subjectId = selectedSubjectId;
    const topicId = selectedTopicId;
    const examId = selectedExamId;
    await act(async () => {
      if (kind === "subject") {
        const saved = await api.updateSubject(id, { name });
        setSubjects((items) => replace(items, saved));
      } else if (kind === "topic") {
        const saved = await api.updateTopic(id, { name });
        if (activeSubjectId.current === subjectId) {
          setTopics((items) => replace(items, saved));
        }
      } else {
        const saved = await api.updateExam(id, { name });
        if (isActiveExam(subjectId, examId)) {
          setExams((items) => replace(items, saved));
        }
      }
      onAcademicDataChanged?.();
      onPlannerInputsChanged?.();
    }, () => kind === "exam"
      ? isActiveExam(subjectId, examId)
      : activeSubjectId.current === subjectId && (
        kind === "subject" || activeTopicId.current === topicId
      ));
  }

  async function remove(kind: "subject" | "topic" | "exam", id: string) {
    if (!window.confirm("Delete this item?")) return;
    const subjectId = selectedSubjectId;
    const topicId = selectedTopicId;
    await act(async () => {
      if (kind === "subject") {
        await api.deleteSubject(id);
        setSubjects((items) => items.filter((item) => item.id !== id));
        if (activeSubjectId.current === id) onSubjectSelected("");
      } else if (kind === "topic") {
        await api.deleteTopic(id);
        if (activeSubjectId.current === subjectId) {
          setTopics((items) => items.filter((item) => item.id !== id));
          if (activeTopicId.current === id) onTopicSelected(subjectId, "");
        }
      } else {
        await api.deleteExam(id);
        onPlannerInputsChanged?.();
        if (activeSubjectId.current === subjectId) {
          setExams((items) => items.filter((item) => item.id !== id));
          if (activeExamId.current === id) {
            activeExamId.current = "";
            setSelectedExamId("");
          }
        }
      }
      onAcademicDataChanged?.();
    }, () => activeSubjectId.current === subjectId && (
      kind !== "topic" || activeTopicId.current === topicId
    ));
  }

  async function removeAssignment(topicId: string) {
    const subjectId = selectedSubjectId;
    const examId = selectedExamId;
    await act(async () => {
      await api.deleteExamTopic(examId, topicId);
      onPlannerInputsChanged?.();
      if (!isActiveExam(subjectId, examId)) return;
      setAssignments((items) => items.filter((item) => item.topic_id !== topicId));
    }, () => isActiveExam(subjectId, examId));
  }

  function chooseSubject(id: string) {
    activeSubjectId.current = id;
    activeTopicId.current = "";
    activeExamId.current = "";
    onSubjectSelected(id);
    setTopics([]);
    setExams([]);
    setSelectedExamId("");
    setAssignments([]);
  }

  function chooseExam(id: string) {
    activeExamId.current = id;
    setSelectedExamId(id);
    setAssignments([]);
  }

  function isActiveExam(subjectId: string, examId: string): boolean {
    return activeSubjectId.current === subjectId && activeExamId.current === examId;
  }

  async function act(action: () => Promise<void>, publishError = () => true) {
    setError("");
    try {
      await action();
    } catch (reason) {
      if (publishError()) setError(errorMessage(reason));
    }
  }

  if (loading) return <p className="panel">Loading subjects…</p>;

  return (
    <section className="space-y-6" aria-labelledby="academic-setup-heading">
      <div className="section-introduction">
        <p className="eyebrow">Curriculum and exams</p>
        <h2 id="academic-setup-heading">Academic setup</h2>
        <p className="empty">Create Subjects and Topics, then connect them to future Exams.</p>
      </div>
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
              <button type="button" aria-pressed={subject.id === selectedSubjectId} className="item-main" onClick={() => chooseSubject(subject.id)}><strong>{subject.name}</strong><span>{subject.description || "No description"}</span></button>
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
          <TopicList
            items={topics}
            selectedTopicId={selectedTopicId}
            onSelect={(item) => onTopicSelected(selectedSubjectId, item.id)}
            onRename={(item) => rename("topic", item.id, item.name)}
            onDelete={(item) => remove("topic", item.id)}
          />
        </section>

        <section className="panel">
          <p className="eyebrow">{selectedSubject.name}</p><h2>Exams</h2>
          <form className="form-grid" onSubmit={createExam}>
            <input aria-label="Exam name" required placeholder="Exam name" value={examForm.name} onChange={(event) => setExamForm({ ...examForm, name: event.target.value })} />
            <input aria-label="Exam date" required type="datetime-local" value={examForm.examDate} onChange={(event) => setExamForm({ ...examForm, examDate: event.target.value })} />
            <input aria-label="Exam description" placeholder="Description (optional)" value={examForm.description} onChange={(event) => setExamForm({ ...examForm, description: event.target.value })} />
            <button type="submit">Add exam</button>
          </form>
          {exams.length === 0 ? <p className="empty">Create a future Exam for this Subject.</p> : <ul className="item-list">{exams.map((exam) => (
            <li key={exam.id} className={exam.id === selectedExamId ? "selected" : ""}>
              <button type="button" aria-pressed={exam.id === selectedExamId} className="item-main" onClick={() => chooseExam(exam.id)}><strong>{exam.name}</strong><span>{new Date(exam.exam_date).toLocaleString()}</span></button>
              <button className="quiet" onClick={() => void rename("exam", exam.id, exam.name)}>Rename</button>
              <button className="danger" onClick={() => void remove("exam", exam.id)}>Delete</button>
            </li>
          ))}</ul>}
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
        {assignments.length === 0 ? <p className="empty">Assign at least one Topic so this Exam can contribute recommendations.</p> : <ul className="item-list">{assignments.map((item) => (
          <li key={item.topic_id}><div className="item-main"><strong>{topics.find((topic) => topic.id === item.topic_id)?.name ?? "Topic"}</strong><span>Weight {item.weight}</span></div><button className="danger" onClick={() => void removeAssignment(item.topic_id)}>Remove</button></li>
        ))}</ul>}
      </section>}
    </section>
  );
}

function TopicList({ items, selectedTopicId, onSelect, onRename, onDelete }: { items: Topic[]; selectedTopicId: string; onSelect: (item: Topic) => void; onRename: (item: Topic) => Promise<void>; onDelete: (item: Topic) => Promise<void> }) {
  if (!items.length) return <p className="empty">Add a Topic to define what you want to practice.</p>;
  return <ul className="item-list">{items.map((item) => <li key={item.id} className={item.id === selectedTopicId ? "selected" : ""}><button type="button" aria-pressed={item.id === selectedTopicId} className="item-main" onClick={() => onSelect(item)}><strong>{item.name}</strong><span>{item.description || "No description"}</span></button><button className="quiet" onClick={() => void onRename(item)}>Rename</button><button className="danger" onClick={() => void onDelete(item)}>Delete</button></li>)}</ul>;
}

function replace<T extends { id: string }>(items: T[], saved: T): T[] {
  return items.map((item) => item.id === saved.id ? saved : item);
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "Something went wrong";
}
