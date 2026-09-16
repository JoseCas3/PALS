"use client";

import { FormEvent, useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";

import { ApiError, api } from "../lib/api";
import type { Document } from "../lib/types";

export function DocumentManager({ selectedSubjectId }: { selectedSubjectId: string }) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState("");
  const [processingId, setProcessingId] = useState("");
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const activeSubjectId = useRef(selectedSubjectId);
  const contextRequest = useRef(0);
  const uploadRequest = useRef(0);
  const deleteRequest = useRef(0);
  const processRequest = useRef(0);

  useLayoutEffect(() => {
    activeSubjectId.current = selectedSubjectId;
  }, [selectedSubjectId]);

  useEffect(() => {
    const subjectId = selectedSubjectId;
    const request = ++contextRequest.current;
    uploadRequest.current += 1;
    deleteRequest.current += 1;
    processRequest.current += 1;
    queueMicrotask(() => {
      if (!isActive(subjectId, request)) return;
      setDocuments([]);
      setFile(null);
      setUploading(false);
      setDeletingId("");
      setProcessingId("");
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

  async function processDocument(documentId: string) {
    if (processingId) return;
    const subjectId = selectedSubjectId;
    const context = contextRequest.current;
    const request = ++processRequest.current;
    setProcessingId(documentId);
    setError("");
    setDocuments((items) => items.map((item) => item.id === documentId
      ? { ...item, status: "PROCESSING", error_code: null }
      : item));
    try {
      const processed = await api.processDocument(documentId);
      if (request !== processRequest.current || !isActive(subjectId, context)) return;
      setDocuments((items) => items.map((item) => item.id === documentId ? processed : item));
    } catch (reason) {
      if (request !== processRequest.current || !isActive(subjectId, context)) return;
      const code = reason instanceof ApiError
        ? reason.code ?? "PROCESSING_FAILED"
        : "PROCESSING_FAILED";
      setDocuments((items) => items.map((item) => item.id === documentId
        ? { ...item, status: "FAILED", error_code: code }
        : item));
      setError(processFailureMessage(code));
    } finally {
      if (request === processRequest.current && isActive(subjectId, context)) {
        setProcessingId("");
      }
    }
  }

  return (
    <section className="panel space-y-5" aria-labelledby="documents-heading">
      <div>
        <p className="eyebrow">Subject resources</p>
        <h2 id="documents-heading">Documents</h2>
        <p className="empty">Process PDFs for grounded Tutor answers and source evidence.</p>
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
              disabled={Boolean(processingId)}
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
            <button type="submit" disabled={!file || uploading || Boolean(processingId)}>
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
                    <Link href={`/documents/${encodeURIComponent(document.id)}`}>
                      <strong>{document.original_filename}</strong>
                    </Link>
                    <span>{document.status} · {formatBytes(document.size_bytes)}</span>
                    {document.status === "FAILED" && (
                      <span>{processFailureMessage(document.error_code)}</span>
                    )}
                  </div>
                  {(document.status === "UPLOADED" || document.status === "FAILED") && (
                    <button
                      type="button"
                      disabled={Boolean(processingId) || Boolean(deletingId)}
                      onClick={() => void processDocument(document.id)}
                    >
                      {processingId === document.id
                        ? "Processing..."
                        : document.status === "FAILED" ? "Retry" : "Process"}
                    </button>
                  )}
                  {document.status === "PROCESSING" && <span>Processing...</span>}
                  <Link
                    className="quiet"
                    href={`/documents/${encodeURIComponent(document.id)}`}
                    aria-label={`View Document ${document.original_filename}`}
                  >
                    View
                  </Link>
                  <button
                    type="button"
                    className="danger"
                    disabled={Boolean(deletingId) || Boolean(processingId)}
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

function processFailureMessage(code: string | null | undefined): string {
  if (code === "TEXT_EXTRACTION_INSUFFICIENT") {
    return "Not enough extractable text. This PDF may be scanned or image-only; OCR is not available yet.";
  }
  if (code === "TEXT_EXTRACTION_FAILED") {
    return "Text could not be extracted from this PDF.";
  }
  if (code === "CHUNKING_FAILED") {
    return "The extracted text could not be prepared for study.";
  }
  return "Document processing failed. You can retry.";
}
