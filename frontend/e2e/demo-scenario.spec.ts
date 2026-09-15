import { expect, test } from "@playwright/test";

import { DEMO_ACCOUNTS, loginAs } from "./helpers";

/**
 * Covers the PRD's Section 24 demo scenario end-to-end:
 *   Overview -> anomaly -> Failure Explorer -> Fingerprint -> RCA
 *   -> Create Incident -> Create Intervention -> before/after impact
 *
 * Runs against the seeded synthetic dataset with its injected
 * BANK_A x Android x U28 x v4.2.1 x 18:00-20:00 anomaly -- no test data is
 * created or mocked here, this is the real demo data.
 */
test.describe("Demo scenario: detect -> diagnose -> intervene -> measure", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, DEMO_ACCOUNTS.pm);
  });

  test("Overview shows the anomaly and links into RCA", async ({ page }) => {
    await expect(page.getByText("Payment Intelligence")).toBeVisible();
    await expect(page.getByText(/anomaly detected/i)).toBeVisible({ timeout: 10_000 });
    await page.getByText(/anomaly detected/i).click();
    await expect(page).toHaveURL(/\/rca/);
  });

  test("Failure Explorer's known-anomaly preset surfaces the injected segment", async ({ page }) => {
    await page.goto("/failures");
    await page.getByRole("button", { name: "Load known anomaly" }).click();

    await expect(page.getByText("BANK_A")).toBeVisible();
    const failureRateCard = page.locator("text=Failure Rate").locator("..");
    await expect(failureRateCard).toBeVisible();
  });

  test("RCA Workspace identifies the correct fingerprint for the injected window", async ({ page }) => {
    await page.goto("/rca");
    await expect(page.getByText("BANK_A × Android × U28 × 4.2.1")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/probable contributor/i)).toBeVisible();
    await expect(page.getByText("RECOMMENDED ACTIONS")).toBeVisible();
  });

  test("full journey: create incident, create intervention, measure real impact", async ({ page }) => {
    await page.goto("/rca");
    await expect(page.getByText("BANK_A × Android × U28 × 4.2.1")).toBeVisible({ timeout: 10_000 });

    await page.getByRole("button", { name: "Create Incident" }).click();
    await expect(page.getByText("INCIDENT CREATED")).toBeVisible();

    await page.getByRole("button", { name: "Create Intervention" }).click();
    await expect(page.getByText(/intervention .* created/i)).toBeVisible();

    await page.getByRole("button", { name: "Measure Impact" }).click();
    await expect(page).toHaveURL(/\/interventions\//);

    await page.getByRole("button", { name: "Measure Impact" }).click();
    await expect(page.getByText("BEFORE / AFTER")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/guardrail/i)).toBeVisible();
  });

  test("created incident appears in the Incidents list and supports a status transition", async ({ page }) => {
    await page.goto("/rca");
    await expect(page.getByText("BANK_A × Android × U28 × 4.2.1")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Create Incident" }).click();
    await page.getByRole("button", { name: "View Incident" }).click();

    await expect(page).toHaveURL(/\/incidents\//);
    await expect(page.getByText("open")).toBeVisible();

    await page.getByRole("button", { name: "investigating" }).click();
    await expect(page.getByText("investigating").first()).toBeVisible();
  });
});
