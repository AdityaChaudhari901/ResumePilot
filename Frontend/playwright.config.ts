import { defineConfig, devices } from "@playwright/test";

function readPort(name: string, fallback: number): number {
  const value = process.env[name];
  if (!value) {
    return fallback;
  }

  const port = Number(value);
  if (!Number.isInteger(port) || port < 1024 || port > 65_535) {
    throw new Error(`${name} must be an integer between 1024 and 65535.`);
  }
  return port;
}

function readRunId(): string {
  const runId = process.env.RESUMEPILOT_E2E_RUN_ID ?? String(Date.now());
  if (!/^[A-Za-z0-9_-]+$/.test(runId)) {
    throw new Error("RESUMEPILOT_E2E_RUN_ID may contain only letters, numbers, _ and -.");
  }
  return runId;
}

const backendPort = readPort("RESUMEPILOT_E2E_BACKEND_PORT", 8040);
const frontendPort = readPort("RESUMEPILOT_E2E_FRONTEND_PORT", 3040);
const backendBaseUrl = `http://127.0.0.1:${backendPort}`;
const frontendBaseUrl = `http://127.0.0.1:${frontendPort}`;
const runId = readRunId();
const backendDataDir = `.local/e2e/${runId}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: {
    timeout: 10_000
  },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  outputDir: ".local/playwright-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: ".local/playwright-report", open: "never" }]
  ],
  use: {
    baseURL: frontendBaseUrl,
    screenshot: "only-on-failure",
    trace: "retain-on-failure"
  },
  webServer: [
    {
      command: `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      cwd: "../Backend",
      env: {
        DATABASE_URL: `sqlite:///./${backendDataDir}/playwright-smoke.db`,
        DEV_USER_PLAN: "premium",
        DEV_USER_SUBSCRIPTION_STATUS: "active",
        JOBCOPILOT_API_TOKEN: "test-token",
        RESUMEPILOT_DATA_DIR: backendDataDir,
        PATH: [process.env.PATH, "/opt/homebrew/bin", "/usr/local/bin"]
          .filter(Boolean)
          .join(":")
      },
      reuseExistingServer: false,
      timeout: 30_000,
      url: `${backendBaseUrl}/health`
    },
    {
      command: `npm run build && npm run start -- -H 127.0.0.1 -p ${frontendPort}`,
      env: {
        AUTH_TRUSTED_PROXY_SECRET: "test-auth-proxy-secret",
        RESUMEPILOT_ALLOW_LOCAL_AUTH_IN_PRODUCTION: "true",
        RESUMEPILOT_API_BASE_URL: backendBaseUrl,
        RESUMEPILOT_AUTH_PROVIDER: "local"
      },
      reuseExistingServer: false,
      timeout: 120_000,
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
