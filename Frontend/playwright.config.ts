import { defineConfig, devices } from "@playwright/test";

const backendPort = Number(process.env.RESUMEPILOT_E2E_BACKEND_PORT ?? 8040);
const frontendPort = Number(process.env.RESUMEPILOT_E2E_FRONTEND_PORT ?? 3040);
const backendBaseUrl = `http://127.0.0.1:${backendPort}`;
const frontendBaseUrl = `http://127.0.0.1:${frontendPort}`;
const reuseExistingServer = process.env.RESUMEPILOT_E2E_REUSE_SERVER === "1";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: {
    timeout: 10_000
  },
  fullyParallel: false,
  workers: 1,
  outputDir: ".local/playwright-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: ".local/playwright-report", open: "never" }]
  ],
  use: {
    baseURL: frontendBaseUrl,
    trace: "retain-on-failure"
  },
  webServer: [
    {
      command:
        "cd ../Backend && " +
        "DATABASE_URL=sqlite:///./.local/data/playwright-smoke.db " +
        "RESUMEPILOT_DATA_DIR=.local/data " +
        "JOBCOPILOT_API_TOKEN=test-token " +
        `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      reuseExistingServer,
      timeout: 30_000,
      url: `${backendBaseUrl}/health`
    },
    {
      command: [
        `RESUMEPILOT_API_BASE_URL=${backendBaseUrl}`,
        `npm run start -- -H 127.0.0.1 -p ${frontendPort}`
      ].join(" "),
      reuseExistingServer,
      timeout: 30_000,
      url: frontendBaseUrl
    }
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
