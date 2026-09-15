import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DocumentManager } from "./document-manager";

const firstDocument = document("document-1", "subject-1", "notes.pdf");

describe("DocumentManager", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows the no-Subject and empty Subject states", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);
    const view = render(<DocumentManager selectedSubjectId="" />);
    expect(screen.getByText("Choose a Subject to manage its Documents.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    view.rerender(<DocumentManager selectedSubjectId="subject-1" />);
    expect(await screen.findByText("No Documents uploaded for this Subject.")).toBeInTheDocument();
  });

  it("renders Subject Documents and minimal metadata", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([firstDocument])));
    render(<DocumentManager selectedSubjectId="subject-1" />);

    expect(await screen.findByText("notes.pdf")).toBeInTheDocument();
    expect(screen.getByText("UPLOADED · 2.0 KB")).toBeInTheDocument();
  });

  it("uploads a PDF and updates the list without a reload", async () => {
    const fetchMock = vi.fn(async (_input: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "POST") return jsonResponse(firstDocument, 201);
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<DocumentManager selectedSubjectId="subject-1" />);
    await screen.findByText("No Documents uploaded for this Subject.");

    const file = new File(["%PDF-1.4"], "notes.pdf", { type: "application/pdf" });
    const input = screen.getByLabelText("Document PDF");
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.submit(input.closest("form")!);

    expect(await screen.findByText("notes.pdf")).toBeInTheDocument();
    const uploadCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(uploadCall?.[1]?.body).toBeInstanceOf(FormData);
    expect(uploadCall?.[1]?.headers).not.toHaveProperty("Content-Type");
  });

  it("shows safe upload validation errors", async () => {
    const fetchMock = vi.fn(async (_input: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "POST") {
        return jsonResponse({ error: { message: "Only PDF documents are supported" } }, 415);
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<DocumentManager selectedSubjectId="subject-1" />);
    await screen.findByText("No Documents uploaded for this Subject.");
    const file = new File(["text"], "notes.txt", { type: "text/plain" });
    const input = screen.getByLabelText("Document PDF");
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.submit(input.closest("form")!);

    expect(await screen.findByRole("alert")).toHaveTextContent("Only PDF documents are supported");
  });

  it("deletes a Document and updates the list", async () => {
    const fetchMock = vi.fn(async (_input: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "DELETE") return emptyResponse();
      return jsonResponse([firstDocument]);
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
    render(<DocumentManager selectedSubjectId="subject-1" />);

    await screen.findByText("notes.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(await screen.findByText("No Documents uploaded for this Subject.")).toBeInTheDocument();
  });

  it("ignores a stale list after the Subject changes", async () => {
    let resolveFirst: ((value: object) => void) | undefined;
    const pendingFirst = new Promise<object>((resolve) => { resolveFirst = resolve; });
    const secondDocument = document("document-2", "subject-2", "physics.pdf");
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      if (input.toString().includes("subject-1")) return pendingFirst;
      return jsonResponse([secondDocument]);
    });
    vi.stubGlobal("fetch", fetchMock);
    const view = render(<DocumentManager selectedSubjectId="subject-1" />);
    view.rerender(<DocumentManager selectedSubjectId="subject-2" />);
    expect(await screen.findByText("physics.pdf")).toBeInTheDocument();

    resolveFirst?.(jsonResponse([firstDocument]));
    await waitFor(() => expect(screen.queryByText("notes.pdf")).not.toBeInTheDocument());
    expect(screen.getByText("physics.pdf")).toBeInTheDocument();
  });

  it.each(["success", "failure"] as const)(
    "ignores a stale upload %s after the Subject changes",
    async (outcome) => {
      let resolveUpload: ((value: object) => void) | undefined;
      const pendingUpload = new Promise<object>((resolve) => { resolveUpload = resolve; });
      const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        if (init?.method === "POST") return pendingUpload;
        if (input.toString().includes("subject-2")) return jsonResponse([]);
        return jsonResponse([]);
      });
      vi.stubGlobal("fetch", fetchMock);
      const view = render(<DocumentManager selectedSubjectId="subject-1" />);
      await screen.findByText("No Documents uploaded for this Subject.");
      const file = new File(["%PDF-1.4"], "notes.pdf", { type: "application/pdf" });
      const input = screen.getByLabelText("Document PDF");
      fireEvent.change(input, { target: { files: [file] } });
      fireEvent.submit(input.closest("form")!);
      view.rerender(<DocumentManager selectedSubjectId="subject-2" />);

      resolveUpload?.(outcome === "success"
        ? jsonResponse(firstDocument, 201)
        : jsonResponse({ error: { message: "Stale upload error" } }, 500));
      await screen.findByText("No Documents uploaded for this Subject.");
      expect(screen.queryByText("notes.pdf")).not.toBeInTheDocument();
      expect(screen.queryByText("Stale upload error")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Upload PDF" })).toBeDisabled();
    },
  );

  it.each(["success", "failure"] as const)(
    "ignores a stale delete %s after the Subject changes",
    async (outcome) => {
      let resolveDelete: ((value: object) => void) | undefined;
      const pendingDelete = new Promise<object>((resolve) => { resolveDelete = resolve; });
      const secondDocument = document("document-2", "subject-2", "physics.pdf");
      const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        if (init?.method === "DELETE") return pendingDelete;
        if (input.toString().includes("subject-2")) return jsonResponse([secondDocument]);
        return jsonResponse([firstDocument]);
      });
      vi.stubGlobal("fetch", fetchMock);
      vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
      const view = render(<DocumentManager selectedSubjectId="subject-1" />);
      await screen.findByText("notes.pdf");
      fireEvent.click(screen.getByRole("button", { name: "Delete" }));
      view.rerender(<DocumentManager selectedSubjectId="subject-2" />);
      expect(await screen.findByText("physics.pdf")).toBeInTheDocument();

      resolveDelete?.(outcome === "success"
        ? emptyResponse()
        : jsonResponse({ error: { message: "Stale delete error" } }, 500));
      await waitFor(() => expect(screen.queryByText("Stale delete error")).not.toBeInTheDocument());
      expect(screen.getByText("physics.pdf")).toBeInTheDocument();
    },
  );

  it("shows lifecycle-specific Process, Processing, Ready, and Retry controls", async () => {
    const uploaded = document("uploaded", "subject-1", "uploaded.pdf");
    const processing = document("processing", "subject-1", "processing.pdf", "PROCESSING");
    const ready = document("ready", "subject-1", "ready.pdf", "READY");
    const failed = document(
      "failed",
      "subject-1",
      "scanned.pdf",
      "FAILED",
      "TEXT_EXTRACTION_INSUFFICIENT",
    );
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      jsonResponse([uploaded, processing, ready, failed]),
    ));
    render(<DocumentManager selectedSubjectId="subject-1" />);

    await screen.findByText("uploaded.pdf");
    expect(screen.getByRole("button", { name: "Process" })).toBeInTheDocument();
    expect(screen.getByText("Processing...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.getByText(/OCR is not available yet/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /ready/i })).not.toBeInTheDocument();
  });

  it("updates the active Document after successful processing", async () => {
    const ready = document("document-1", "subject-1", "notes.pdf", "READY");
    const fetchMock = vi.fn(async (_input: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "POST") return jsonResponse(ready);
      return jsonResponse([firstDocument]);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<DocumentManager selectedSubjectId="subject-1" />);
    await screen.findByRole("button", { name: "Process" });

    fireEvent.click(screen.getByRole("button", { name: "Process" }));

    await waitFor(() => expect(screen.queryByRole("button", { name: "Process" }))
      .not.toBeInTheDocument());
    expect(screen.getByText(/READY/)).toBeInTheDocument();
  });

  it("publishes a safe FAILED state after processing fails", async () => {
    const fetchMock = vi.fn(async (_input: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "POST") {
        return jsonResponse({
          error: {
            code: "TEXT_EXTRACTION_INSUFFICIENT",
            message: "PDF does not contain enough extractable text",
          },
        }, 422);
      }
      return jsonResponse([firstDocument]);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<DocumentManager selectedSubjectId="subject-1" />);
    await screen.findByRole("button", { name: "Process" });

    fireEvent.click(screen.getByRole("button", { name: "Process" }));

    expect(await screen.findByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.getAllByText(/OCR is not available yet/).length).toBeGreaterThan(0);
    expect(screen.queryByText("TEXT_EXTRACTION_INSUFFICIENT")).not.toBeInTheDocument();
  });

  it.each(["success", "failure"] as const)(
    "ignores a stale process %s after the Subject changes",
    async (outcome) => {
      let resolveProcess: ((value: object) => void) | undefined;
      const pendingProcess = new Promise<object>((resolve) => { resolveProcess = resolve; });
      const secondDocument = document("document-2", "subject-2", "physics.pdf");
      const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        if (init?.method === "POST") return pendingProcess;
        if (input.toString().includes("subject-2")) return jsonResponse([secondDocument]);
        return jsonResponse([firstDocument]);
      });
      vi.stubGlobal("fetch", fetchMock);
      const view = render(<DocumentManager selectedSubjectId="subject-1" />);
      await screen.findByRole("button", { name: "Process" });
      fireEvent.click(screen.getByRole("button", { name: "Process" }));
      view.rerender(<DocumentManager selectedSubjectId="subject-2" />);
      await screen.findByText("physics.pdf");

      resolveProcess?.(outcome === "success"
        ? jsonResponse(document("document-1", "subject-1", "notes.pdf", "READY"))
        : jsonResponse({
          error: { code: "PROCESSING_FAILED", message: "Stale process error" },
        }, 500));

      await waitFor(() => expect(screen.queryByText("notes.pdf")).not.toBeInTheDocument());
      expect(screen.queryByText("Stale process error")).not.toBeInTheDocument();
      expect(screen.getByText("physics.pdf")).toBeInTheDocument();
    },
  );

  it("ignores a stale retry completion after the Subject changes", async () => {
    let resolveRetry: ((value: object) => void) | undefined;
    const pendingRetry = new Promise<object>((resolve) => { resolveRetry = resolve; });
    const failed = document("document-1", "subject-1", "failed.pdf", "FAILED");
    const secondDocument = document("document-2", "subject-2", "physics.pdf");
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      if (init?.method === "POST") return pendingRetry;
      if (input.toString().includes("subject-2")) return jsonResponse([secondDocument]);
      return jsonResponse([failed]);
    });
    vi.stubGlobal("fetch", fetchMock);
    const view = render(<DocumentManager selectedSubjectId="subject-1" />);
    await screen.findByRole("button", { name: "Retry" });
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    view.rerender(<DocumentManager selectedSubjectId="subject-2" />);
    await screen.findByText("physics.pdf");

    resolveRetry?.(jsonResponse(document("document-1", "subject-1", "failed.pdf", "READY")));
    await waitFor(() => expect(screen.queryByText("failed.pdf")).not.toBeInTheDocument());
    expect(screen.getByText("physics.pdf")).toBeInTheDocument();
  });
});

function document(
  id: string,
  subjectId: string,
  filename: string,
  status: "UPLOADED" | "PROCESSING" | "READY" | "FAILED" = "UPLOADED",
  errorCode: string | null = null,
) {
  return {
    id,
    subject_id: subjectId,
    original_filename: filename,
    mime_type: "application/pdf",
    size_bytes: 2048,
    checksum_sha256: "a".repeat(64),
    status,
    error_code: errorCode,
    processing_version: 1,
    embedding_provider: null,
    embedding_model: null,
    embedding_dimensions: null,
    created_at: "2026-09-13T00:00:00Z",
    updated_at: "2026-09-13T00:00:00Z",
  };
}

function jsonResponse(payload: object, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(payload) };
}

function emptyResponse() {
  return { ok: true, status: 204, json: vi.fn() };
}
