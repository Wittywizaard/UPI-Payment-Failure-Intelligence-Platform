import { expect, test } from "@playwright/test";

test.describe("Authentication", () => {
  test("unauthenticated user visiting a protected route is redirected to login", async ({ page }) => {
    await page.goto("/incidents");
    await expect(page).toHaveURL(/\/login/);
  });

  test("login page shows demo account picker for all 6 roles", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText("Admin")).toBeVisible();
    await expect(page.getByText("Product Manager")).toBeVisible();
    await expect(page.getByText("Payment Ops")).toBeVisible();
    await expect(page.getByText("Engineer")).toBeVisible();
    await expect(page.getByText("Support")).toBeVisible();
    await expect(page.getByText("Viewer")).toBeVisible();
  });

  test("wrong password shows an error and does not navigate away", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("pm@upi-fip.dev");
    await page.getByLabel("Password").fill("wrong-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert")).toContainText(/incorrect|invalid/i);
    await expect(page).toHaveURL(/\/login/);
  });

  test("correct credentials log in and land on the Overview dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("pm@upi-fip.dev");
    await page.getByLabel("Password").fill("Demo123!");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL("/");
    await expect(page.getByText("Payment Intelligence")).toBeVisible();
  });

  test("sign out returns to login and re-guards protected routes", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("pm@upi-fip.dev");
    await page.getByLabel("Password").fill("Demo123!");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL("/");

    await page.getByTitle("Sign out").click();
    await expect(page).toHaveURL(/\/login/);

    await page.goto("/incidents");
    await expect(page).toHaveURL(/\/login/);
  });
});
