import path from "node:path";

import { expect, type Page, test, type TestInfo } from "@playwright/test";

const RESUME_FIXTURE = path.resolve(
  process.cwd(),
  "../Backend/evals/resumes/backend_fresher.md"
);
const SAMPLE_JOB_POSTING_PATH = "/sample-job-posting.html";
const BACKEND_PLATFORM_JOB_PATH = "/backend-platform-job.html";
const DATA_API_JOB_PATH = "/data-api-job.html";

test("dashboard demo flow renders report and validates exports", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const reportId = await completeDashboardDemoFlow(page);

  await expectReportExport(page, `/api/reports/${reportId}/markdown`, {
    contentDisposition: null,
    contentType: "text/plain",
    prefix: "# Job Fit Report"
  });
  await expectReportExport(page, `/api/reports/${reportId}/resume/latex`, {
    contentDisposition: `attachment; filename="resumepilot-report-${reportId}.tex"`,
    contentType: "application/x-tex",
    prefix: "%-------------------------"
  });
  await expectReportExport(page, `/api/reports/${reportId}/resume/docx`, {
    contentDisposition: `attachment; filename="resumepilot-report-${reportId}.docx"`,
    contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    prefix: "PK"
  });
  await expectReportExport(page, `/api/reports/${reportId}/resume/pdf`, {
    contentDisposition: `attachment; filename="resumepilot-report-${reportId}.pdf"`,
    contentType: "application/pdf",
    prefix: "%PDF-"
  });

  await captureDashboardScreenshot(page, testInfo, "dashboard-desktop.png");
});

test("dashboard demo flow remains usable on mobile", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 1200 });
  await completeDashboardDemoFlow(page);

  await expect(page.getByRole("link", { name: "Markdown" })).toBeVisible();
  await expect(page.getByRole("link", { name: "DOCX" })).toBeVisible();
  await expect(page.getByRole("link", { name: "LaTeX" })).toBeVisible();
  await expect(page.getByRole("link", { name: "PDF" })).toBeVisible();

  await captureDashboardScreenshot(page, testInfo, "dashboard-mobile.png");
});

test("dashboard sends a job posting URL analysis request", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto("/");

  await page.getByLabel("Resume file").setInputFiles(RESUME_FIXTURE);
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText(/Resume ID \d+/)).toBeVisible({ timeout: 15_000 });

  const jobUrl = "https://example.com/jobs/backend-engineer";
  const capturedPayloads: Record<string, unknown>[] = [];

  await page.route("**/api/jobs/analyze", async (route) => {
    capturedPayloads.push(
      JSON.parse(route.request().postData() ?? "{}") as Record<string, unknown>
    );
    await route.fulfill({
      body: JSON.stringify({ detail: "mocked URL analysis request" }),
      contentType: "application/json",
      status: 400
    });
  });

  await page.getByRole("textbox", { name: "Job posting URL" }).fill(jobUrl);
  await page.getByRole("textbox", { name: "Company" }).fill("Example");
  await page.getByRole("textbox", { name: "Role" }).fill("Backend Engineer");
  await page.getByRole("button", { name: "Analyze" }).click();

  await expect(page.getByText("mocked URL analysis request")).toBeVisible();
  await expect.poll(() => capturedPayloads[0]?.job_url).toBe(jobUrl);
  expect(capturedPayloads[0]?.job_text).toBeNull();
  expect(capturedPayloads[0]?.company).toBe("Example");
  expect(capturedPayloads[0]?.role).toBe("Backend Engineer");
});

test("report ledger reopens the selected saved report accurately", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto("/");

  await page.getByLabel("Resume file").setInputFiles(RESUME_FIXTURE);
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText(/Resume ID \d+/)).toBeVisible({ timeout: 15_000 });

  const firstReportId = await analyzeJob(page, {
    company: "Ledger Labs",
    role: "Backend Platform Engineer",
    url: jobPostingUrl(page, BACKEND_PLATFORM_JOB_PATH)
  });

  const secondReportId = await analyzeJob(page, {
    company: "Insight Works",
    role: "Data API Engineer",
    url: jobPostingUrl(page, DATA_API_JOB_PATH)
  });

  expect(secondReportId).not.toBe(firstReportId);

  await expect(page.getByRole("button", { name: /Data API Engineer/ })).toHaveAttribute(
    "aria-current",
    "true"
  );

  await page.getByRole("button", { name: /Backend Platform Engineer/ }).click();
  await expect(page.getByRole("button", { name: /Backend Platform Engineer/ })).toHaveAttribute(
    "aria-current",
    "true"
  );
  await expect(page.getByRole("link", { name: "LaTeX" })).toHaveAttribute(
    "href",
    `/api/reports/${firstReportId}/resume/latex`
  );
});

async function completeDashboardDemoFlow(page: Page): Promise<string> {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Application review console" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Session" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Report ledger" })).toBeVisible();
  await expect(page.getByText("No saved reports yet.")).toBeVisible();
  await expect(page.getByText("authenticated", { exact: true })).toBeVisible();

  await page.getByLabel("Resume file").setInputFiles(RESUME_FIXTURE);
  await expect(page.getByText("backend_fresher.md")).toBeVisible();

  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText(/Resume ID \d+/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Resume extraction" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Parsed skills" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence ledger" })).toBeVisible();

  await page.getByRole("button", { name: "Sample" }).click();
  await expect(page.getByRole("textbox", { name: "Company" })).toHaveValue("NovaHire AI");
  await expect(page.getByRole("textbox", { name: "Role" })).toHaveValue("Backend Engineer");
  await expect(page.getByRole("textbox", { name: "Job posting URL" })).toHaveValue(
    jobPostingUrl(page, SAMPLE_JOB_POSTING_PATH)
  );

  await page.getByRole("button", { name: "Analyze" }).click();
  await expect(page.getByRole("heading", { name: "Evidence-backed fit" })).toBeVisible({
    timeout: 30_000
  });
  await expect(page.getByText("Match score")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Matched skills" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Missing or weak" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ATS keywords" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Next actions" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Workflow trace" })).toBeVisible();
  await expect(page.getByText(/Report \d+/).first()).toBeVisible();
  await expect(page.getByText("Deterministic fallback")).toBeVisible();
  await expect(page.getByText(/\d+(?:\.\d)? (?:ms|s) total/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Plan usage" })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Analyses usage" })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Exports usage" })).toBeVisible();

  const latexHref = await page.getByRole("link", { name: "LaTeX" }).getAttribute("href");
  return extractReportId(latexHref);
}

interface AnalyzeJobInput {
  company: string;
  role: string;
  url: string;
}

async function analyzeJob(page: Page, input: AnalyzeJobInput): Promise<string> {
  await page.getByRole("textbox", { name: "Company" }).fill(input.company);
  await page.getByRole("textbox", { name: "Role" }).fill(input.role);
  await page.getByRole("textbox", { name: "Job posting URL" }).fill(input.url);
  await page.getByRole("button", { name: "Analyze" }).click();
  await expect(page.getByRole("heading", { name: "Evidence-backed fit" })).toBeVisible({
    timeout: 30_000
  });
  const latexHref = await page.getByRole("link", { name: "LaTeX" }).getAttribute("href");
  return extractReportId(latexHref);
}

function jobPostingUrl(page: Page, pathName: string): string {
  return new URL(pathName, page.url()).toString();
}

interface ExpectedExport {
  contentDisposition: string | null;
  contentType: string;
  prefix: string;
}

async function expectReportExport(
  page: Page,
  exportPath: string,
  expected: ExpectedExport
): Promise<void> {
  const exportUrl = new URL(exportPath, page.url()).toString();
  const response = await page.request.get(exportUrl);

  expect(response.status(), exportPath).toBe(200);
  expect(response.headers()["content-type"], exportPath).toContain(expected.contentType);

  if (expected.contentDisposition) {
    expect(response.headers()["content-disposition"], exportPath).toBe(
      expected.contentDisposition
    );
  } else {
    expect(response.headers()["content-disposition"], exportPath).toBeUndefined();
  }

  const body = await response.body();
  expect(body.subarray(0, expected.prefix.length).toString("latin1"), exportPath).toBe(
    expected.prefix
  );
}

async function captureDashboardScreenshot(
  page: Page,
  testInfo: TestInfo,
  fileName: string
): Promise<void> {
  await page.screenshot({
    fullPage: true,
    path: testInfo.outputPath(fileName)
  });
}

function extractReportId(latexHref: string | null): string {
  if (!latexHref) {
    throw new Error("LaTeX export link did not include an href.");
  }

  const match = latexHref.match(/^\/api\/reports\/(\d+)\/resume\/latex$/);
  if (!match?.[1]) {
    throw new Error(`Unexpected LaTeX export href: ${latexHref}`);
  }

  return match[1];
}
