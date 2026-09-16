import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DocumentDetail } from "./document-detail";

const documentId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const chunkId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const document = {
  id: documentId,
  subject_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  original_filename: "<img src=x onerror=alert(1)>.pdf",
  mime_type: "application/pdf",
  size_bytes: 2048,
  checksum_sha256: "a".repeat(64),
  status: "READY",
  error_code: null,
  processing_version: 1,
  embedding_provider: "fake",
  embedding_model: "fake-deterministic-v1",
  embedding_dimensions: 1536,
  created_at: "2026-09-15T00:00:00Z",
  updated_at: "2026-09-15T00:00:00Z",
};

describe("DocumentDetail", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads metadata and exact citation evidence as escaped plain text", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      if (input.toString().endsWith(`/chunks/${chunkId}`)) {
        return jsonResponse({
          chunk_id: chunkId,
          document_id: documentId,
          document_filename: document.original_filename,
          page_start: 2,
          page_end: 4,
          text: "Quoted evidence\n<script>alert('evidence')</script>",
        });
      }
      return jsonResponse(document);
    });
    vi.stubGlobal("fetch", fetchMock);

    const view = render(<DocumentDetail documentId={documentId} chunkId={chunkId} />);

    expect(await screen.findByRole("heading", { name: document.original_filename }))
      .toBeInTheDocument();
    expect(screen.getByText("Pages 2–4")).toBeInTheDocument();
    expect(screen.getByText(/<script>alert\('evidence'\)<\/script>/)).toBeInTheDocument();
    expect(view.container.querySelector("script")).toBeNull();
    expect(view.container.querySelector("img")).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows metadata without fabricating evidence when no chunk is supplied", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(document));
    vi.stubGlobal("fetch", fetchMock);

    render(<DocumentDetail documentId={documentId} chunkId={null} />);

    expect(await screen.findByRole("heading", { name: document.original_filename }))
      .toBeInTheDocument();
    expect(screen.getByText(/Open this Document from a Tutor citation/)).toBeInTheDocument();
    expect(screen.queryByText("Quoted evidence")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("handles a missing or deleted Document", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      jsonResponse({ error: { code: "DOCUMENT_NOT_FOUND", message: "Document not found" } }, 404),
    ));

    render(<DocumentDetail documentId={documentId} chunkId={chunkId} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Source document is no longer available.",
    );
  });

  it("handles unavailable citation evidence without stale text", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) =>
      input.toString().endsWith(`/chunks/${chunkId}`)
        ? jsonResponse({
          error: { code: "DOCUMENT_EVIDENCE_NOT_FOUND", message: "Not found" },
        }, 404)
        : jsonResponse(document));
    vi.stubGlobal("fetch", fetchMock);

    render(<DocumentDetail documentId={documentId} chunkId={chunkId} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Cited evidence is no longer available",
    );
    expect(screen.queryByText("Quoted evidence")).not.toBeInTheDocument();
  });

  it("switches to the deleted-source state if the Document disappears before evidence loads", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) =>
      input.toString().endsWith(`/chunks/${chunkId}`)
        ? jsonResponse({
          error: { code: "DOCUMENT_NOT_FOUND", message: "Document not found" },
        }, 404)
        : jsonResponse(document));
    vi.stubGlobal("fetch", fetchMock);

    render(<DocumentDetail documentId={documentId} chunkId={chunkId} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Source document is no longer available.",
    );
    expect(screen.queryByRole("heading", { name: document.original_filename }))
      .not.toBeInTheDocument();
  });

  it("rejects a malformed chunk target without requesting evidence", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(document));
    vi.stubGlobal("fetch", fetchMock);

    render(<DocumentDetail documentId={documentId} chunkId="not-a-uuid" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("citation target is invalid");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows a safe generic API error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 500)));

    render(<DocumentDetail documentId={documentId} chunkId={chunkId} />);

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(
      "Document details could not be loaded.",
    ));
  });
});

function jsonResponse(payload: object, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  };
}
