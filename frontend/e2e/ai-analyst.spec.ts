import { expect, test } from "@playwright/test";

import { DEMO_ACCOUNTS, loginAs } from "./helpers";

test.describe("AI Analyst", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, DEMO_ACCOUNTS.pm);
    await page.goto("/ai-analyst");
  });

  test("shows suggested questions before any question is asked", async ({ page }) => {
    await expect(page.getByText("Why did PSR drop yesterday?")).toBeVisible();
    await expect(page.getByText("Which bank contributed most to failures?")).toBeVisible();
  });

  test("clicking a suggested question returns a grounded, evidence-backed answer", async ({ page }) => {
    await page.getByText("Why did PSR drop yesterday?").click();

    await expect(page.getByText(/BANK_A/)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/probable contributor/i)).toBeVisible();
    await expect(page.getByText("yesterday")).toBeVisible();
  });

  test("typing a free-form question about value at risk returns a real figure", async ({ page }) => {
    await page.getByPlaceholder(/ask about your payment data/i).fill("What is the value at risk yesterday?");
    await page.getByRole("button", { name: "Ask" }).click();

    await expect(page.getByText(/₹/)).toBeVisible({ timeout: 15_000 });
  });

  test("an out-of-range question states insufficient data rather than guessing", async ({ page }) => {
    await page.getByPlaceholder(/ask about your payment data/i).fill("What is the value at risk today?");
    await page.getByRole("button", { name: "Ask" }).click();

    await expect(page.getByText(/don't have enough data/i)).toBeVisible({ timeout: 15_000 });
  });
});
