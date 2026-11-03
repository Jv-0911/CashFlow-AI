import { defineConfig } from "@playwright/test";
import { randomUUID } from "node:crypto";
const runId = process.env.CASHFLOW_E2E_RUN_ID ?? randomUUID();
process.env.CASHFLOW_E2E_RUN_ID = runId;
const python = process.env.CASHFLOW_TEST_PYTHON ?? "python";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  expect: { timeout: 10000 },
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:8010",
    headless: true,
    channel: process.env.CASHFLOW_BROWSER_CHANNEL || undefined,
    screenshot: "only-on-failure",
    trace: "off",
  },
  webServer: [
    {
      command: `${python} -B -m tests.e2e.serve --port 8010 --run-id ${runId}`,
      cwd: "..",
      url: "http://127.0.0.1:8010/health",
      reuseExistingServer: false,
      timeout: 120000,
    },
    {
      command: `${python} -B -m tests.e2e.serve --port 8011 --run-id ${runId} --authenticated`,
      cwd: "..",
      url: "http://127.0.0.1:8011/health",
      reuseExistingServer: false,
      timeout: 120000,
    },
  ],
});
