import type { Page } from "@playwright/test";

export async function loginAs(page: Page, email: string, password = "Demo123!") {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("/");
}

export const DEMO_ACCOUNTS = {
  admin: "admin@upi-fip.dev",
  pm: "pm@upi-fip.dev",
  ops: "ops@upi-fip.dev",
  engineer: "engineer@upi-fip.dev",
  support: "support@upi-fip.dev",
  viewer: "viewer@upi-fip.dev",
};
