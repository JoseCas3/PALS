import { execFileSync } from "node:child_process";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { syntheticPdf } from "./pdf-fixtures";

const repositoryRoot = path.resolve(__dirname, "../../..");

function persistedChunkCount(filename: string): number {
  const query =
    "SELECT count(*) FROM document_chunks c JOIN documents d ON d.id=c.document_id " +
    `WHERE d.original_filename='${filename}';`;
  return Number(execFileSync(
    "docker",
    [
      "compose", "-p", "pals-e2e", "-f", "docker-compose.e2e.yml",
      "exec", "-T", "postgres-e2e", "psql", "-U", "pals", "-d", "pals_e2e_test",
      "-tAc", query,
    ],
    { cwd: repositoryRoot, encoding: "utf8" },
  ).trim());
}

test("publishes fake embeddings and safely rejects insufficient PDFs", async ({ page }) => {
  const subjectName = "R3 Embedding Subject";

  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();

  await page.getByLabel("Subject name").fill(subjectName);
  await page.getByRole("button", { name: "Add subject" }).click();
  await expect(page.getByRole("button", { name: new RegExp(subjectName) }).first())
    .toHaveAttribute("aria-pressed", "true");

  const documents = page.getByRole("region", { name: "Documents" });
  await documents.getByLabel("Document PDF").setInputFiles({
    name: "text-one-page.pdf",
    mimeType: "application/pdf",
    buffer: syntheticPdf([
      "This synthetic course page contains enough deterministic text for local PDF processing.",
    ]),
  });
  await documents.getByRole("button", { name: "Upload PDF" }).click();
  const textDocument = documents.getByRole("listitem").filter({ hasText: "text-one-page.pdf" });
  await expect(textDocument.getByText(/UPLOADED/)).toBeVisible();
  await textDocument.getByRole("button", { name: "Process" }).click();
  await expect(textDocument.getByText(/READY/)).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: new RegExp(subjectName) }).first().click();
  await expect(documents.getByText("text-one-page.pdf")).toBeVisible();
  await expect(documents.getByRole("listitem").filter({ hasText: "text-one-page.pdf" })
    .getByText(/READY/)).toBeVisible();
  expect(persistedChunkCount("text-one-page.pdf")).toBeGreaterThan(0);

  await documents.getByLabel("Document PDF").setInputFiles({
    name: "empty-text.pdf",
    mimeType: "application/pdf",
    buffer: syntheticPdf([""]),
  });
  await documents.getByRole("button", { name: "Upload PDF" }).click();
  const emptyDocument = documents.getByRole("listitem").filter({ hasText: "empty-text.pdf" });
  await emptyDocument.getByRole("button", { name: "Process" }).click();
  await expect(emptyDocument.getByText(/OCR is not available yet/)).toBeVisible();
  await expect(emptyDocument.getByRole("button", { name: "Retry" })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await emptyDocument.getByRole("button", { name: "Delete" }).click();
  await expect(documents.getByText("empty-text.pdf")).not.toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await textDocument.getByRole("button", { name: "Delete" }).click();
  await expect(documents.getByText("text-one-page.pdf")).not.toBeVisible();
  expect(persistedChunkCount("text-one-page.pdf")).toBe(0);
  await expect(documents.getByText("No Documents uploaded for this Subject.")).toBeVisible();
});
