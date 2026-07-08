import path from "node:path";

import { expect, type Page, test, type TestInfo } from "@playwright/test";

const RESUME_FIXTURE = path.resolve(
  process.cwd(),
  "../Backend/evals/resumes/backend_fresher.md"
);

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
  await expect(page.getByRole("link", { name: "LaTeX" })).toBeVisible();
  await expect(page.getByRole("link", { name: "PDF" })).toBeVisible();

  await captureDashboardScreenshot(page, testInfo, "dashboard-mobile.png");
});

async function completeDashboardDemoFlow(page: Page): Promise<string> {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Application review console" })).toBeVisible();

  await page.getByLabel("Resume file").setInputFiles(RESUME_FIXTURE);
  await expect(page.getByText("backend_fresher.md")).toBeVisible();

  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText(/Resume ID \d+/)).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "Sample" }).click();
  await expect(page.getByRole("textbox", { name: "Company" })).toHaveValue("NovaHire AI");
  await expect(page.getByRole("textbox", { name: "Role" })).toHaveValue("Backend Engineer");
  await expect(page.getByRole("textbox", { name: "Job description" })).toHaveValue(
    /Required Python/
  );

  await page.getByRole("button", { name: "Analyze" }).click();
  await expect(page.getByRole("heading", { name: "Evidence-backed fit" })).toBeVisible({
    timeout: 30_000
  });
  await expect(page.getByText("Match score")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Matched skills" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Missing or weak" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Workflow trace" })).toBeVisible();
  await expect(page.getByText("Deterministic fallback")).toBeVisible();
  await expect(page.getByText(/\d+(?:\.\d)? (?:ms|s) total/)).toBeVisible();

  const latexHref = await page.getByRole("link", { name: "LaTeX" }).getAttribute("href");
  return extractReportId(latexHref);
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
