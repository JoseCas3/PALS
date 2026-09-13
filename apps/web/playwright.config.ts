import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  use: {
    baseURL: "http://localhost:3100",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev -- --port 3100",
    cwd: path.resolve(__dirname),
    env: {
      ...process.env,
      NEXT_PUBLIC_API_URL: "http://localhost:8100",
    },
    url: "http://localhost:3100",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
