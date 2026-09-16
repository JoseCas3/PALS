"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, api } from "../lib/api";
import type { Document, DocumentEvidence } from "../lib/types";
import { formatPageRange } from "./grounded-citation";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

type Failure = "DOCUMENT_NOT_FOUND" | "EVIDENCE_NOT_FOUND" | "INVALID_TARGET" | "ERROR";

export function DocumentDetail({
  documentId,
  chunkId,
}: {
  documentId: string;
  chunkId: string | null;
}) {
  return (
    <DocumentDetailState
      key={`${documentId}:${chunkId ?? "document"}`}
      documentId={documentId}
      chunkId={chunkId}
    />
  );
}

function DocumentDetailState({
  documentId,
  chunkId,
}: {
  documentId: string;
  chunkId: string | null;
}) {
  const [document, setDocument] = useState<Document | null>(null);
  const [evidence, setEvidence] = useState<DocumentEvidence | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    void api.getDocument(documentId)
      .then(async (loadedDocument) => {
        if (!active) return;
        setDocument(loadedDocument);
        if (chunkId === null) return;
        if (!UUID_PATTERN.test(chunkId)) {
          setFailure("INVALID_TARGET");
          return;
        }
        try {
          const loadedEvidence = await api.getDocumentEvidence(documentId, chunkId);
          if (active) setEvidence(loadedEvidence);
        } catch (reason) {
          if (!active) return;
          if (reason instanceof ApiError && reason.code === "DOCUMENT_NOT_FOUND") {
            setFailure("DOCUMENT_NOT_FOUND");
          } else if (
            reason instanceof ApiError && reason.code === "DOCUMENT_EVIDENCE_NOT_FOUND"
          ) {
            setFailure("EVIDENCE_NOT_FOUND");
          } else {
            setFailure("ERROR");
          }
        }
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setFailure(
          reason instanceof ApiError && reason.code === "DOCUMENT_NOT_FOUND"
            ? "DOCUMENT_NOT_FOUND"
            : "ERROR",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [chunkId, documentId]);

  if (loading) {
    return <p role="status" className="empty">Loading Document…</p>;
  }
  if (failure === "DOCUMENT_NOT_FOUND") {
    return <UnavailableState message="Source document is no longer available." />;
  }
  if (!document) {
    return <UnavailableState message="Document details could not be loaded." />;
  }

  return (
    <article className="document-detail">
      <section className="panel" aria-labelledby="document-metadata-heading">
        <p className="eyebrow">Document</p>
        <h1 id="document-metadata-heading">{document.original_filename}</h1>
        <dl className="document-metadata">
          <div><dt>Status</dt><dd>{document.status}</dd></div>
          <div><dt>Uploaded</dt><dd>{formatDate(document.created_at)}</dd></div>
          <div><dt>Size</dt><dd>{formatBytes(document.size_bytes)}</dd></div>
        </dl>
      </section>

      <section className="panel source-evidence" aria-labelledby="source-evidence-heading">
        <p className="eyebrow">Grounded Tutor provenance</p>
        <h2 id="source-evidence-heading">Source evidence</h2>
        {chunkId === null ? (
          <p className="empty">
            Open this Document from a Tutor citation to inspect the cited evidence.
          </p>
        ) : failure === "INVALID_TARGET" ? (
          <p role="alert" className="error-banner">The citation target is invalid.</p>
        ) : failure === "EVIDENCE_NOT_FOUND" ? (
          <p role="alert" className="error-banner">
            Cited evidence is no longer available for this Document.
          </p>
        ) : failure === "ERROR" ? (
          <p role="alert" className="error-banner">Source evidence could not be loaded.</p>
        ) : evidence ? (
          <>
            <p className="evidence-location">
              {formatPageRange(evidence.page_start, evidence.page_end)}
            </p>
            <p className="evidence-note">
              This excerpt was used as source material for the grounded Tutor response.
            </p>
            <pre className="evidence-text">{evidence.text}</pre>
          </>
        ) : null}
      </section>
    </article>
  );
}

function UnavailableState({ message }: { message: string }) {
  return (
    <section className="panel unavailable-source">
      <p role="alert" className="error-banner">{message}</p>
      <Link href="/">Return to PALS</Link>
    </section>
  );
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  return `${(size / 1024).toFixed(1)} KB`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}
