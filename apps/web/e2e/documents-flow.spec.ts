import path from "node:path";

import { expect, test } from "@playwright/test";

test("persists and deletes a Subject PDF without AI", async ({ page }) => {
  const subjectName = "R1 Document Subject";
  const fixture = path.resolve(__dirname, "fixtures/r1-synthetic.pdf");

  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();

  await page.getByLabel("Subject name").fill(subjectName);
  await page.getByRole("button", { name: "Add subject" }).click();
  await expect(page.getByRole("button", { name: new RegExp(subjectName) }).first())
    .toHaveAttribute("aria-pressed", "true");

  const documents = page.getByRole("region", { name: "Documents" });
  await documents.getByLabel("Document PDF").setInputFiles(fixture);
  await documents.getByRole("button", { name: "Upload PDF" }).click();
  await expect(documents.getByText("r1-synthetic.pdf")).toBeVisible();
  await expect(documents.getByText(/UPLOADED/)).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: new RegExp(subjectName) }).first().click();
  await expect(documents.getByText("r1-synthetic.pdf")).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await documents.getByRole("button", { name: "Delete" }).click();
  await expect(documents.getByText("r1-synthetic.pdf")).not.toBeVisible();
  await expect(documents.getByText("No Documents uploaded for this Subject.")).toBeVisible();
});
