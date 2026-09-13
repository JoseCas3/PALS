import { expect, test } from "@playwright/test";

test("completes the deterministic Alpha learning loop without AI", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("API connected")).toBeVisible();

  await page.getByLabel("Subject name").fill("Alpha Calculus");
  await page.getByLabel("Subject description").fill("E2E curriculum");
  await page.getByRole("button", { name: "Add subject" }).click();
  await expect(page.getByRole("button", { name: /Alpha Calculus/ }).first()).toHaveAttribute("aria-pressed", "true");

  await page.getByLabel("Topic name").fill("Limits");
  await page.getByRole("button", { name: "Add topic" }).click();
  await expect(page.getByText("Alpha Calculus / Limits")).toBeVisible();

  await page.getByLabel("Exam name").fill("Alpha Final");
  await page.getByLabel("Exam date").fill("2099-12-01T12:00");
  await page.getByRole("button", { name: "Add exam" }).click();

  await page.getByLabel("Topic to assign").selectOption({ label: "Limits" });
  await page.getByLabel("Topic weight").fill("1");
  await page.getByRole("button", { name: "Save weight" }).click();

  const recommendation = page.getByLabel("Study this now");
  await expect(recommendation).toContainText("Limits");
  await expect(recommendation).toContainText("Mastery0.00");
  await recommendation.getByRole("button", { name: "Practice this topic" }).click();
  await expect(page.getByText("Alpha Calculus / Limits")).toBeVisible();
  await expect(page.getByLabel("Practice topic")).toHaveValue(/.+/);

  await page.getByLabel("Question prompt").fill("What value does x approach?");
  await page.getByLabel("Answer reference").fill("The limiting value.");
  await page.getByRole("button", { name: "Add question" }).click();
  await expect(page.getByText("Show answer reference")).toBeVisible();

  await page.getByLabel("Time spent seconds").fill("30");
  await page.getByRole("button", { name: "Record attempt" }).click();
  await expect(page.getByText("Attempt recorded. Mastery updated to 8.00.")).toBeVisible();
  await expect(page.getByLabel("Current mastery")).toContainText("8.00");
  await expect(recommendation).toContainText("Mastery8.00");
  await expect(page.getByText("Alpha Calculus / Limits")).toBeVisible();

  const academicSetup = page.getByRole("region", { name: "Academic setup" });
  const topicsPanel = academicSetup.getByRole("heading", { name: "Topics" }).locator("..");
  page.once("dialog", (dialog) => dialog.accept());
  await topicsPanel.getByRole("button", { name: "Delete" }).click();
  await expect(academicSetup.getByRole("alert")).toContainText("cannot be deleted");

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(recommendation.getByRole("button", { name: "Practice this topic" })).toBeVisible();
  await expect(page.getByLabel("Practice topic")).toBeVisible();
});
