import { expect, test } from "@playwright/test";

import { syntheticPdf } from "./pdf-fixtures";

test("navigates from a grounded Tutor citation to exact source evidence", async ({ page }) => {
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
  const sourceLink = page.getByRole("link", {
    name: "View source S1: grounded-course.pdf, Page 1 (opens in new tab)",
  });
  await expect(sourceLink).toBeVisible();
  const sourcePagePromise = page.waitForEvent("popup");
  await sourceLink.click();
  const sourcePage = await sourcePagePromise;

  await expect(sourcePage).toHaveURL(/\/documents\/[0-9a-f-]+\?chunk=[0-9a-f-]+$/);
  await expect(sourcePage.getByRole("heading", { name: "grounded-course.pdf" })).toBeVisible();
  await expect(sourcePage.getByRole("heading", { name: "Source evidence" })).toBeVisible();
  await expect(sourcePage.getByText("Page 1", { exact: true })).toBeVisible();
  await expect(sourcePage.getByText(/A derivative measures instantaneous rate of change/))
    .toBeVisible();
  await expect(page.getByLabel("Tutor response")).toContainText(
    "Use the supplied source evidence",
  );
});
