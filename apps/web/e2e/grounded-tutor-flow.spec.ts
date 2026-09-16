import { expect, test } from "@playwright/test";

import { syntheticPdf } from "./pdf-fixtures";

test("returns a grounded Tutor answer with a server-issued source", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();

  await page.getByLabel("Subject name").fill("Grounded Tutor Subject");
  await page.getByRole("button", { name: "Add subject" }).click();

  const documents = page.getByRole("region", { name: "Documents" });
  await documents.getByLabel("Document PDF").setInputFiles({
    name: "grounded-course.pdf",
    mimeType: "application/pdf",
    buffer: syntheticPdf([
      "A derivative measures instantaneous rate of change and slope of a tangent line.",
    ]),
  });
  await documents.getByRole("button", { name: "Upload PDF" }).click();
  const document = documents.getByRole("listitem").filter({ hasText: "grounded-course.pdf" });
  await document.getByRole("button", { name: "Process" }).click();
  await expect(document.getByText(/READY/)).toBeVisible();

  await page.getByLabel("Topic name").fill("Derivatives");
  await page.getByRole("button", { name: "Add topic" }).click();
  await page.getByLabel("Question prompt").fill("What does a derivative measure?");
  await page.getByLabel("Answer reference").fill("Instantaneous rate of change.");
  await page.getByRole("button", { name: "Add question" }).click();

  await page.getByLabel("Ground this answer in my Subject documents").check();
  await page.getByRole("button", { name: "Get help" }).click();

  await expect(page.getByLabel("Tutor response")).toContainText(
    "Use the supplied source evidence",
  );
  await expect(page.getByLabel("Tutor sources")).toContainText(
    "S1 — grounded-course.pdf, p. 1",
  );
});
