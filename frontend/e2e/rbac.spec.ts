import { expect, test } from "@playwright/test";

import { DEMO_ACCOUNTS, loginAs } from "./helpers";

test.describe("RBAC in the UI", () => {
  test("viewer sees a read-only notice on RCA instead of write actions", async ({ page }) => {
    await loginAs(page, DEMO_ACCOUNTS.viewer);
    await page.goto("/rca");
    await expect(page.getByText("BANK_A × Android × U28 × 4.2.1")).toBeVisible({ timeout: 10_000 });

    await expect(page.getByText(/can view this RCA but cannot create/i)).toBeVisible();
    await expect(page.getByRole("button", { name: "Create Incident" })).toHaveCount(0);
  });

  test("viewer cannot see note/status-transition controls on an incident they can still view", async ({ page }) => {
    await loginAs(page, DEMO_ACCOUNTS.pm);
    await page.goto("/rca");
    await expect(page.getByText("BANK_A × Android × U28 × 4.2.1")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Create Incident" }).click();
    await page.getByRole("button", { name: "View Incident" }).click();
    const incidentUrl = page.url();

    await page.getByTitle("Sign out").click();
    await loginAs(page, DEMO_ACCOUNTS.viewer);
    await page.goto(incidentUrl);

    await expect(page.getByRole("button", { name: "investigating" })).toHaveCount(0);
    await expect(page.getByPlaceholder(/add a note/i)).toHaveCount(0);
  });

  test("settings page highlights the signed-in user's row in the permission matrix", async ({ page }) => {
    await loginAs(page, DEMO_ACCOUNTS.engineer);
    await page.goto("/settings");
    await expect(page.getByText("(you)")).toBeVisible();
  });
});
