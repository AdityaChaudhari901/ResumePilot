import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test, type TestInfo } from "@playwright/test";

const RESUME_FIXTURE = path.resolve(
  process.cwd(),
  "../Backend/evals/resumes/backend_fresher.md"
);
const SAMPLE_JOB_POSTING_PATH = "/sample-job-posting.html";
const BACKEND_PLATFORM_JOB_PATH = "/backend-platform-job.html";
const DATA_API_JOB_PATH = "/data-api-job.html";
const UNCLEAR_JOB_POSTING_PATH = "/unclear-job-posting.html";

test("dashboard enforces browser security headers and an accessibility baseline", async ({
  page
}) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const response = await page.goto("/");
  if (!response) {
    throw new Error("Dashboard navigation completed without an HTTP response.");
  }

  expect(response.status()).toBe(200);
  expect(response.headers()["x-content-type-options"]).toBe("nosniff");
  expect(response.headers()["x-frame-options"]).toBe("DENY");
  expect(response.headers()["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  expect(response.headers()["permissions-policy"]).toBe(
    "camera=(), geolocation=(), microphone=()"
  );

  await expect(page.getByRole("heading", { name: "Guided application workflow" })).toBeVisible();
  await page.waitForLoadState("networkidle");

  const accessibilityScan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const violations = accessibilityScan.violations.map((violation) => ({
    help: violation.help,
    id: violation.id,
    impact: violation.impact,
    targets: violation.nodes.flatMap((node) => node.target)
  }));

  expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
});

test("dashboard demo flow renders report and validates exports", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const { applicationId, reportId } = await completeDashboardDemoFlow(page);

  await expectReportExport(page, `/api/reports/${reportId}/markdown`, {
    contentDisposition: `attachment; filename="resumepilot-report-${reportId}.md"`,
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
  await expectReportExport(page, `/api/applications/${applicationId}/tailored-resume/latex`, {
    contentDisposition: `attachment; filename="resumepilot-application-${applicationId}.tex"`,
    contentType: "application/x-tex",
    prefix: "%-------------------------"
  });
  await expectReportExport(page, `/api/applications/${applicationId}/tailored-resume/docx`, {
    contentDisposition: `attachment; filename="resumepilot-application-${applicationId}.docx"`,
    contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    prefix: "PK"
  });
  await expectReportExport(page, `/api/applications/${applicationId}/tailored-resume/pdf`, {
    contentDisposition: `attachment; filename="resumepilot-application-${applicationId}.pdf"`,
    contentType: "application/pdf",
    prefix: "%PDF-"
  });

  await captureDashboardScreenshot(page, testInfo, "dashboard-desktop.png");
});

test("dashboard demo flow remains usable on mobile", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 1200 });
  await completeDashboardDemoFlow(page);

  await expect(page.getByRole("button", { name: "Download Markdown" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download DOCX" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download LaTeX" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download PDF" })).toBeVisible();

  await captureDashboardScreenshot(page, testInfo, "dashboard-mobile.png");
});

test("dashboard sends a job posting URL analysis request", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto("/");

  const jobUrl = "https://example.com/jobs/backend-engineer";
  await page.route("**/api/jobs/preview", async (route) => {
    await route.fulfill({
      body: JSON.stringify({
        job_url: jobUrl,
        profile: {
          benefits: [],
          company: "Example Co",
          employment_type: null,
          experience_level: null,
          job_id: 0,
          keywords: ["Python"],
          location: null,
          preferred_skills: [],
          required_skills: [
            {
              confidence: "high",
              evidence_text: "Required Python experience.",
              id: "job_required_001",
              importance: "required",
              name: "Python"
            }
          ],
          responsibilities: ["Build backend services."],
          role_title: "Backend Engineer",
          unclear_items: [],
          warnings: []
        },
        parser: "generic_html",
        quality_checks: [
          {
            code: "required_or_preferred_skills",
            message: "Required or preferred skills were extracted.",
            status: "pass"
          }
        ],
        raw_text_char_count: 120,
        status: "ready"
      }),
      contentType: "application/json",
      status: 200
    });
  });

  await page.getByRole("textbox", { name: "Job listing URL" }).fill(jobUrl);
  await expect(page.getByRole("textbox", { name: "Company" })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Role" })).toHaveCount(0);
  await page.getByRole("button", { name: "Review job evidence" }).click();
  await expect(page.getByRole("heading", { name: "Review job evidence" })).toBeVisible();
  await page.getByRole("textbox", { name: "Role" }).fill("Reviewed Backend Engineer");
  await page.getByRole("button", { name: "Save and continue" }).click();

  await page.getByLabel("Resume file").setInputFiles(RESUME_FIXTURE);
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByRole("heading", { name: "AI services" })).toBeVisible({
    timeout: 15_000
  });

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

  await page.getByRole("button", { name: "Run AI analysis" }).click();

  await expect(page.getByText("mocked URL analysis request")).toBeVisible();
  await expect.poll(() => capturedPayloads[0]?.job_url).toBe(jobUrl);
  expect(capturedPayloads[0]?.job_text).toBeNull();
  expect(capturedPayloads[0]?.company).toBeNull();
  expect(capturedPayloads[0]?.role).toBeNull();
  expect(capturedPayloads[0]?.application_id).toEqual(expect.any(Number));
  expect(capturedPayloads[0]?.reviewed_job_profile).toMatchObject({
    company: "Example Co",
    required_skills: [{ name: "Python" }],
    role_title: "Reviewed Backend Engineer"
  });
});

test("dashboard flags unclear job requirement extraction", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await mockFixtureJobPreviews(page);
  await page.goto("/");

  await page.getByRole("textbox", { name: "Job listing URL" }).fill(
    jobPostingUrl(page, UNCLEAR_JOB_POSTING_PATH)
  );
  await page.getByRole("button", { name: "Review job evidence" }).click();
  await expect(page.getByRole("heading", { name: "Review job evidence" })).toBeVisible();
  await expect(page.getByText("Job evidence needs review")).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with warning" })).toBeVisible();
  await page.getByRole("button", { name: "Continue with warning" }).click();
  await uploadResume(page);
  await runAiAnalysis(page);

  await expect(page.getByText("Provisional score", { exact: true })).toBeVisible();
  await expect(page.getByText("Needs job details", { exact: true })).toBeVisible();
  await expect(page.getByText("Job details need review", { exact: true })).toBeVisible();
  await expect(page.getByText("No evidence-backed matches yet", { exact: true })).toBeVisible();
  await expect(page.getByText("Gaps not available", { exact: true })).toBeVisible();
  await expect(page.getByText("No ATS keywords extracted", { exact: true })).toBeVisible();
});

test("report ledger reopens the selected saved report accurately", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await mockFixtureJobPreviews(page);
  await page.goto("/");

  await enterJobListing(page, {
    url: jobPostingUrl(page, BACKEND_PLATFORM_JOB_PATH)
  });
  await uploadResume(page);
  const firstReportId = (await runAiAnalysis(page)).reportId;

  const secondReportId = await analyzeJob(page, {
    url: jobPostingUrl(page, DATA_API_JOB_PATH)
  });

  expect(secondReportId).not.toBe(firstReportId);

  await page.getByText("Workspace review and system status").click();
  await expect(page.getByRole("button", { name: /Data API Engineer/ })).toHaveAttribute(
    "aria-current",
    "true"
  );

  await page.getByRole("button", { name: /Backend Platform Engineer/ }).click();
  await expect(page.getByRole("button", { name: /Backend Platform Engineer/ })).toHaveAttribute(
    "aria-current",
    "true"
  );
  const exportResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/api/reports/${firstReportId}/resume/latex`)
  );
  await page.getByRole("button", { name: "Download LaTeX" }).click();
  expect((await exportResponsePromise).status()).toBe(200);
});

interface CompletedDashboardFlow {
  applicationId: string;
  reportId: string;
}

interface RunAiAnalysisResult {
  applicationId: string | null;
  reportId: string;
}

async function completeDashboardDemoFlow(page: Page): Promise<CompletedDashboardFlow> {
  await mockFixtureJobPreviews(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Guided application workflow" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Application workflow" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Job listing" })).toBeVisible();

  await page.getByText("Workspace review and system status").click();
  await expect(page.getByRole("heading", { name: "Session" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Application pipeline" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Report ledger" })).toBeVisible();
  await expect(page.getByText("authenticated", { exact: true })).toBeVisible();

  await page.getByRole("textbox", { name: "Job listing URL" }).fill(
    jobPostingUrl(page, SAMPLE_JOB_POSTING_PATH)
  );
  await expect(page.getByRole("textbox", { name: "Company" })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Role" })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Job listing URL" })).toHaveValue(
    jobPostingUrl(page, SAMPLE_JOB_POSTING_PATH)
  );
  await page.getByRole("button", { name: "Review job evidence" }).click();
  await expect(page.getByRole("heading", { name: "Review job evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Required skills" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "required skill name" }).first()).toHaveValue(
    "Python"
  );
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByRole("heading", { name: "Resume upload" })).toBeVisible();
  await expect(page.getByRole("article").filter({ hasText: "Backend Engineer" }).first()).toContainText(
    "Reviewed"
  );

  await page.getByLabel("Resume file").setInputFiles(RESUME_FIXTURE);
  await expect(page.getByText("backend_fresher.md")).toBeVisible();

  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByRole("heading", { name: "AI services" })).toBeVisible();
  await expect(page.getByText("Parse job evidence")).toBeVisible();

  await expect(page.getByRole("heading", { name: "Resume extraction" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Parsed skills" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence ledger" })).toBeVisible();

  const result = await runAiAnalysis(page, { acceptFirstDraft: true });

  await expect(page.getByText("Match score")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Matched skills" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Missing or weak" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ATS keywords" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Next actions" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Workflow trace" })).toBeVisible();
  await expect(page.getByText(/Report \d+/).first()).toBeVisible();
  await expect(page.getByText("Deterministic fallback", { exact: true })).toBeVisible();
  await expect(page.getByText(/\d+(?:\.\d)? (?:ms|s) total/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Plan usage meter" })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Analysis runs usage" })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Exports usage" })).toBeVisible();
  await expect(page.getByRole("article").filter({ hasText: "Backend Engineer" }).first()).toContainText(
    "Report ready"
  );
  await page.getByRole("button", { name: "Applied" }).first().click();
  await expect(page.getByRole("article").filter({ hasText: "Backend Engineer" }).first()).toContainText(
    "Applied"
  );

  const pageText = await page.locator("body").innerText();
  expect(pageText).not.toMatch(/(?:summary|skills)_\d{3} ·/);
  expect(pageText).toMatch(/(?:Project evidence|Work evidence|Resume summary|Skills section) #\d+/);

  if (!result.applicationId) {
    throw new Error("Accepted draft flow did not expose an application export action.");
  }
  return {
    applicationId: result.applicationId,
    reportId: result.reportId
  };
}

interface AnalyzeJobInput {
  url: string;
}

async function analyzeJob(page: Page, input: AnalyzeJobInput): Promise<string> {
  await enterJobListing(page, input);
  return (await runAiAnalysis(page)).reportId;
}

async function enterJobListing(page: Page, input: AnalyzeJobInput): Promise<void> {
  const jobUrlInput = page.getByRole("textbox", { name: "Job listing URL" });
  if (!(await jobUrlInput.isVisible().catch(() => false))) {
    await page.getByRole("button", { name: "Edit job listing" }).click();
  }

  await jobUrlInput.fill(input.url);
  await page.getByRole("button", { name: "Review job evidence" }).click();
  await expect(page.getByRole("heading", { name: "Review job evidence" })).toBeVisible();
  await page.getByRole("button", { name: /^(Save and continue|Continue with warning)$/ }).click();
}

async function uploadResume(page: Page): Promise<void> {
  await expect(page.getByRole("heading", { name: "Resume upload" })).toBeVisible();
  await page.getByLabel("Resume file").setInputFiles(RESUME_FIXTURE);
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByRole("heading", { name: "AI services" })).toBeVisible({
    timeout: 15_000
  });
}

interface FixtureJobPreview {
  company: string | null;
  preferredSkills: string[];
  requiredSkills: string[];
  responsibilities: string[];
  role: string | null;
  unclearItems?: string[];
}

const FIXTURE_JOB_PREVIEWS: Record<string, FixtureJobPreview> = {
  [SAMPLE_JOB_POSTING_PATH]: {
    company: "NovaHire AI",
    preferredSkills: ["Pytest"],
    requiredSkills: ["Python", "FastAPI", "SQL"],
    responsibilities: [
      "Build REST APIs for hiring workflows.",
      "Write reliable tests and validation gates for user-facing reports."
    ],
    role: "Backend Engineer"
  },
  [BACKEND_PLATFORM_JOB_PATH]: {
    company: "Ledger Labs",
    preferredSkills: [],
    requiredSkills: ["Python", "FastAPI", "SQL"],
    responsibilities: [
      "Build REST APIs for internal application workflows.",
      "Improve test coverage for backend services."
    ],
    role: "Backend Platform Engineer"
  },
  [DATA_API_JOB_PATH]: {
    company: "Insight Works",
    preferredSkills: ["Pytest"],
    requiredSkills: ["Python", "REST API"],
    responsibilities: [
      "Build API integrations for analytics workflows.",
      "Work with SQL-backed datasets."
    ],
    role: "Data API Engineer"
  },
  [UNCLEAR_JOB_POSTING_PATH]: {
    company: null,
    preferredSkills: [],
    requiredSkills: [],
    responsibilities: ["Collaborate with product teams on customer-facing software."],
    role: null,
    unclearItems: ["Required and preferred technical skills are not explicit."]
  }
};

async function mockFixtureJobPreviews(page: Page): Promise<void> {
  await page.route("**/api/jobs/preview", async (route) => {
    const payload = JSON.parse(route.request().postData() ?? "{}") as { job_url?: unknown };
    if (typeof payload.job_url !== "string") {
      await route.fallback();
      return;
    }

    const fixture = FIXTURE_JOB_PREVIEWS[new URL(payload.job_url).pathname];
    if (!fixture) {
      await route.fallback();
      return;
    }

    const hasRequirements =
      fixture.requiredSkills.length > 0 || fixture.preferredSkills.length > 0;
    const jobSkills = (skills: string[], importance: "preferred" | "required") =>
      skills.map((name, index) => ({
        confidence: "high",
        evidence_text: `${importance === "required" ? "Required" : "Preferred"} ${name} experience.`,
        id: `job_${importance}_${String(index + 1).padStart(3, "0")}`,
        importance,
        name
      }));

    await route.fulfill({
      body: JSON.stringify({
        job_url: payload.job_url,
        parser: "playwright_fixture",
        profile: {
          benefits: [],
          company: fixture.company,
          employment_type: null,
          experience_level: null,
          job_id: 0,
          keywords: [...fixture.requiredSkills, ...fixture.preferredSkills],
          location: null,
          preferred_skills: jobSkills(fixture.preferredSkills, "preferred"),
          required_skills: jobSkills(fixture.requiredSkills, "required"),
          responsibilities: fixture.responsibilities,
          role_title: fixture.role,
          unclear_items: fixture.unclearItems ?? [],
          warnings: hasRequirements
            ? []
            : [
                {
                  code: "required_skills_unclear",
                  evidence_ids: [],
                  message: "Required and preferred technical skills are not explicit."
                }
              ]
        },
        quality_checks: [
          {
            code: "required_or_preferred_skills",
            message: hasRequirements
              ? "Required or preferred skills were extracted."
              : "Required and preferred skills were not explicit.",
            status: hasRequirements ? "pass" : "fail"
          }
        ],
        raw_text_char_count: hasRequirements ? 480 : 180,
        status: hasRequirements ? "ready" : "missing_requirements"
      }),
      contentType: "application/json",
      status: 200
    });
  });
}

async function runAiAnalysis(
  page: Page,
  options: { acceptFirstDraft?: boolean } = {}
): Promise<RunAiAnalysisResult> {
  await expect(page.getByRole("heading", { name: "AI services" })).toBeVisible();
  await page.getByRole("button", { name: "Run AI analysis" }).click();
  await expect(page.getByRole("heading", { name: "Tailored resume workspace" })).toBeVisible({
    timeout: 30_000
  });

  const draftWorkspace = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Tailored resume workspace" })
  });
  let applicationId: string | null = null;

  if (options.acceptFirstDraft) {
    await expect(draftWorkspace.getByText("Export locked")).toBeVisible();
    const acceptedDraftResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === "PATCH" &&
        response.url().includes("/tailored-resume/items/")
    );
    await draftWorkspace.getByRole("button", { name: "Accept" }).first().click();
    const acceptedDraftResponse = await acceptedDraftResponsePromise;
    expect(acceptedDraftResponse.status()).toBe(200);
    applicationId = String((await acceptedDraftResponse.json()).application_id);
    await expect(draftWorkspace.getByRole("button", { name: "Download DOCX" })).toBeVisible();
  }

  await draftWorkspace.getByRole("button", { name: "View report" }).click();
  await expect(page.getByRole("heading", { name: "Evidence-backed fit" })).toBeVisible({
    timeout: 15_000
  });
  const reportLabel = await page
    .locator('section[aria-label="Active workflow step"]')
    .getByText(/^Report \d+$/)
    .first()
    .textContent();
  const reportId = reportLabel?.match(/\d+/)?.[0];
  if (!reportId) {
    throw new Error(`Could not parse the active report id from: ${reportLabel ?? "missing label"}`);
  }
  return {
    applicationId,
    reportId
  };
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
  const response = await page.request.post(exportUrl);

  expect(response.status(), exportPath).toBe(200);
  expect(response.headers()["content-type"], exportPath).toContain(expected.contentType);

  expect(response.headers()["content-disposition"], exportPath).toBe(expected.contentDisposition);
  expect(response.headers()["cache-control"], exportPath).toContain("private, no-store");

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
