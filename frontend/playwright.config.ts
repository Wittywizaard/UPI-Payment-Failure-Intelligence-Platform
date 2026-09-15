import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";

/**
 * Assumes the full stack (Postgres + backend + frontend, seeded with the
 * synthetic dataset) is already running -- e.g. via `docker compose up` or
 * the manual step-by-step setup in the README -- rather than having
 * Playwright start the servers itself. This matches how these tests run in
 * CI (see docs/decisions.md D42): the stack is brought up once, then both
 * the backend's pytest suite and this Playwright suite run against it.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // tests share seeded demo accounts and mutate incident/intervention state
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
