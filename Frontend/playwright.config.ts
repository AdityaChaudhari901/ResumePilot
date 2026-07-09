import { defineConfig, devices } from "@playwright/test";

const backendPort = Number(process.env.RESUMEPILOT_E2E_BACKEND_PORT ?? 8040);
const frontendPort = Number(process.env.RESUMEPILOT_E2E_FRONTEND_PORT ?? 3040);
const backendBaseUrl = `http://127.0.0.1:${backendPort}`;
const frontendBaseUrl = `http://127.0.0.1:${frontendPort}`;
const reuseExistingServer = process.env.RESUMEPILOT_E2E_REUSE_SERVER === "1";
const runId = process.env.RESUMEPILOT_E2E_RUN_ID ?? String(Date.now());
const backendDataDir = `.local/e2e/${runId}`;

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
        `DATABASE_URL=sqlite:///./${backendDataDir}/playwright-smoke.db ` +
        `RESUMEPILOT_DATA_DIR=${backendDataDir} ` +
        "JOBCOPILOT_API_TOKEN=test-token " +
        "DEV_USER_PLAN=premium " +
        "DEV_USER_SUBSCRIPTION_STATUS=active " +
        `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      reuseExistingServer,
      timeout: 30_000,
      url: `${backendBaseUrl}/health`
    },
    {
      command: [
        `RESUMEPILOT_API_BASE_URL=${backendBaseUrl}`,
        "RESUMEPILOT_AUTH_PROVIDER=local",
        "RESUMEPILOT_ALLOW_LOCAL_AUTH_IN_PRODUCTION=true",
        "AUTH_TRUSTED_PROXY_SECRET=test-auth-proxy-secret",
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
