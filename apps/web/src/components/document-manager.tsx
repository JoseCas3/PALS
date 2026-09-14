"use client";

import { FormEvent, useEffect, useLayoutEffect, useRef, useState } from "react";

import { api } from "../lib/api";
import type { Document } from "../lib/types";

export function DocumentManager({ selectedSubjectId }: { selectedSubjectId: string }) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState("");
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const activeSubjectId = useRef(selectedSubjectId);
  const contextRequest = useRef(0);
  const uploadRequest = useRef(0);
  const deleteRequest = useRef(0);

  useLayoutEffect(() => {
    activeSubjectId.current = selectedSubjectId;
  }, [selectedSubjectId]);

  useEffect(() => {
    const subjectId = selectedSubjectId;
    const request = ++contextRequest.current;
    uploadRequest.current += 1;
    deleteRequest.current += 1;
    queueMicrotask(() => {
      if (!isActive(subjectId, request)) return;
      setDocuments([]);
      setFile(null);
      setUploading(false);
      setDeletingId("");
      setError("");
      setLoading(Boolean(subjectId));
      if (fileInput.current) fileInput.current.value = "";
    });
    if (!subjectId) return;

    void api.listDocuments(subjectId)
      .then((items) => {
        if (isActive(subjectId, request)) setDocuments(items);
      })
      .catch((reason: unknown) => {
        if (isActive(subjectId, request)) setError(errorMessage(reason));
      })
      .finally(() => {
        if (isActive(subjectId, request)) setLoading(false);
      });
  }, [selectedSubjectId]);

  function isActive(subjectId: string, request: number): boolean {
    return activeSubjectId.current === subjectId && contextRequest.current === request;
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!selectedSubjectId || !file || uploading) return;
    const subjectId = selectedSubjectId;
    const context = contextRequest.current;
    const request = ++uploadRequest.current;
    const submittedFile = file;
    setUploading(true);
    setError("");
    try {
      const created = await api.uploadDocument(subjectId, submittedFile);
      if (request !== uploadRequest.current || !isActive(subjectId, context)) return;
      setDocuments((items) => [...items, created]);
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
    } catch (reason) {
      if (request === uploadRequest.current && isActive(subjectId, context)) {
        setError(errorMessage(reason));
      }
    } finally {
      if (request === uploadRequest.current && isActive(subjectId, context)) {
        setUploading(false);
      }
    }
  }

  async function remove(documentId: string) {
    if (!window.confirm("Delete this document?")) return;
    const subjectId = selectedSubjectId;
    const context = contextRequest.current;
    const request = ++deleteRequest.current;
    setDeletingId(documentId);
    setError("");
    try {
      await api.deleteDocument(documentId);
      if (request !== deleteRequest.current || !isActive(subjectId, context)) return;
      setDocuments((items) => items.filter((item) => item.id !== documentId));
    } catch (reason) {
      if (request === deleteRequest.current && isActive(subjectId, context)) {
        setError(errorMessage(reason));
      }
    } finally {
      if (request === deleteRequest.current && isActive(subjectId, context)) {
        setDeletingId("");
      }
    }
  }

  return (
    <section className="panel space-y-5" aria-labelledby="documents-heading">
      <div>
        <p className="eyebrow">Subject resources</p>
        <h2 id="documents-heading">Documents</h2>
        <p className="empty">PDF storage only. Processing and retrieval are not part of R1.</p>
      </div>

      {error && <p role="alert" className="error-banner">{error}</p>}

      {!selectedSubjectId ? (
        <p className="empty">Choose a Subject to manage its Documents.</p>
      ) : (
        <>
          <form className="form-grid" onSubmit={upload}>
            <input
              ref={fileInput}
              aria-label="Document PDF"
              type="file"
              accept="application/pdf,.pdf"
              required
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
            <button type="submit" disabled={!file || uploading}>
              {uploading ? "Uploading…" : "Upload PDF"}
            </button>
          </form>

          {loading ? (
            <p className="empty">Loading Documents…</p>
          ) : documents.length === 0 ? (
            <p className="empty">No Documents uploaded for this Subject.</p>
          ) : (
            <ul className="item-list" aria-label="Subject documents">
              {documents.map((document) => (
                <li key={document.id}>
                  <div className="item-main">
                    <strong>{document.original_filename}</strong>
                    <span>{document.status} · {formatBytes(document.size_bytes)}</span>
                  </div>
                  <button
                    type="button"
                    className="danger"
                    disabled={Boolean(deletingId)}
                    onClick={() => void remove(document.id)}
                  >
                    {deletingId === document.id ? "Deleting…" : "Delete"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  return `${(size / 1024).toFixed(1)} KB`;
}

function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "Document operation failed";
}
