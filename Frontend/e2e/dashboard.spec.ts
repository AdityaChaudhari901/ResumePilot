import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test, type TestInfo } from "@playwright/test";

import type { ApplicationReport } from "@/features/dashboard/types";

const RESUME_FIXTURE = path.resolve(
  process.cwd(),
  "../Backend/evals/resumes/backend_fresher.md"
);
const SAMPLE_JOB_POSTING_PATH = "/sample-job-posting.html";
const BACKEND_PLATFORM_JOB_PATH = "/backend-platform-job.html";
const DATA_API_JOB_PATH = "/data-api-job.html";
const UNCLEAR_JOB_POSTING_PATH = "/unclear-job-posting.html";
const DASHBOARD_PATH = "/app/dashboard";
const WORKFLOW_PATH = "/app/applications/new";

function pendingApprovalOperation() {
  return {
    id: "00000000-0000-4000-8000-000000000777",
    application_id: null,
    kind: "analysis",
    status: "waiting_for_approval",
    stage: "approval_required",
    progress_percent: 90,
    attempt_count: 1,
    max_attempts: 3,
    cancelable: true,
    result: {
      analysis_id: 777,
      report_id: 777,
      match_score: 82,
      scoring_version: "evidence_v2",
      score_status: "scored",
      status: "completed"
    },
    approval: {
      id: "a".repeat(64),
      kind: "live_ai_draft",
      status: "pending",
      title: "Review the validated live draft",
      message: "Approve this evidence-safe proposal or keep the deterministic report.",
      warning_codes: [],
      requested_at: "2026-07-10T08:00:00Z",
      decision: null,
      decided_at: null,
      proposal: {
        executive_summary: "Evidence-safe live summary",
        cover_letter: "Dear Hiring Team,\n\nEvidence-safe live cover letter.",
        interview_questions: [
          {
            category: "Technical",
            questions: ["Which evidence best supports this role?"],
            suggested_answer_evidence_ids: ["project_001"]
          }
        ]
      }
    },
    error: null,
    created_at: "2026-07-10T08:00:00Z",
    updated_at: "2026-07-10T08:01:00Z",
    started_at: "2026-07-10T08:00:01Z",
    finished_at: null
  };
}

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

  await expect(page).toHaveURL(DASHBOARD_PATH);
  await expect(page.getByRole("heading", { name: "Application command center" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Workspace navigation" })).toBeVisible();
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

test("dashboard supports compact dark mode and reduced-motion preferences", async ({ page }, testInfo) => {
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await page.setViewportSize({ width: 320, height: 900 });
  await page.goto(DASHBOARD_PATH);

  await expect(page.getByRole("heading", { name: "Application command center" })).toBeVisible();
  const themeToggle = page.getByRole("button", { name: "Switch to light theme" });
  await expect(themeToggle).toBeVisible();
  expect(await page.locator("html").evaluate((element) => getComputedStyle(element).colorScheme)).toBe(
    "dark"
  );

  const viewport = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth
  }));
  expect(viewport.scrollWidth).toBeLessThanOrEqual(viewport.clientWidth);
  const newApplicationBounds = await page
    .getByRole("link", { name: "New application" })
    .last()
    .boundingBox();
  expect(newApplicationBounds).not.toBeNull();
  expect(newApplicationBounds?.x ?? -1).toBeGreaterThanOrEqual(0);
  expect(
    (newApplicationBounds?.x ?? 0) + (newApplicationBounds?.width ?? 0)
  ).toBeLessThanOrEqual(320);
  await captureDashboardScreenshot(page, testInfo, "workspace-dashboard-mobile.png");

  await themeToggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.getByRole("button", { name: "Switch to dark theme" })).toBeVisible();

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.getByRole("button", { name: "Switch to dark theme" })).toBeVisible();
});

test("workspace navigation keeps applications, reports, and settings on focused pages", async ({
  page
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(DASHBOARD_PATH);

  const navigation = page.getByRole("navigation", { name: "Workspace navigation" });
  await expect(page.getByRole("heading", { name: "Application command center" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Job listing" })).toHaveCount(0);
  await captureDashboardScreenshot(page, testInfo, "workspace-dashboard-desktop.png");

  await navigation.getByRole("link", { name: "Settings" }).click();
  await expect(page).toHaveURL("/app/settings");
  await expect(page.getByRole("heading", { name: "Settings and integrations" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Session" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Plan usage meter" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Job listing" })).toHaveCount(0);

  await navigation.getByRole("link", { name: "Applications" }).click();
  await expect(page).toHaveURL("/app/applications");
  await expect(page.getByRole("heading", { name: "Applications", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "All applications" })).toBeVisible();

  await page.getByRole("link", { name: "New application" }).first().click();
  await expect(page).toHaveURL(WORKFLOW_PATH);
  await expect(page.getByRole("heading", { name: "Guided application workflow" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Job listing" })).toBeVisible();
});

test("not-found routes provide an accessible recovery path", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  const response = await page.goto("/outside-the-evidence-trail");

  expect(response?.status()).toBe(404);
  await expect(
    page.getByRole("heading", { name: "This page is outside the evidence trail." })
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Return to ResumePilot" })).toBeVisible();

  const accessibilityScan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    accessibilityScan.violations.map((violation) => violation.id),
    JSON.stringify(accessibilityScan.violations, null, 2)
  ).toEqual([]);
});

test("dashboard isolates an unlinked durable operation until its case file is ready", async ({
  page
}) => {
  const operation = pendingApprovalOperation();
  await page.route("**/api/operations/active*", async (route) => {
    await route.fulfill({
      body: JSON.stringify({ items: [operation], count: 1 }),
      contentType: "application/json",
      status: 200
    });
  });

  await page.goto(WORKFLOW_PATH);
  await expect(
    page.getByRole("heading", { name: "Finish the analysis already in progress" })
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve live draft" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Cancel analysis" })).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Finish the analysis already in progress" })
  ).toBeVisible();
});

test("dashboard keeps recovery controls after a running operation is rehydrated", async ({
  page
}) => {
  const operation = {
    ...pendingApprovalOperation(),
    approval: null,
    result: null,
    stage: "generating_report",
    status: "running"
  };
  await page.route("**/api/operations/active*", async (route) => {
    await route.fulfill({
      body: JSON.stringify({ items: [operation], count: 1 }),
      contentType: "application/json",
      status: 200
    });
  });

  await page.goto(WORKFLOW_PATH);
  await expect(page.getByRole("button", { name: "Resume status" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel analysis" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run AI analysis" })).toHaveCount(0);
});

test("application routes bind approval controls only to matching operation provenance", async ({
  page
}) => {
  const reviewedJobProfile = {
    benefits: [],
    company: "Role A Company",
    employment_type: null,
    experience_level: null,
    job_id: 101,
    keywords: ["Python"],
    location: null,
    preferred_skills: [],
    required_skills: [
      {
        confidence: "high",
        evidence_text: "Python is required for the role.",
        id: "job_required_001",
        importance: "required",
        name: "Python"
      }
    ],
    responsibilities: ["Build reliable application services."],
    role_title: "Role A",
    unclear_items: [],
    warnings: []
  };
  const applicationA = {
    analysis_id: null,
    company: "Role A Company",
    created_at: "2026-07-11T08:00:00Z",
    id: 101,
    job_id: 101,
    job_url: null,
    match_score: null,
    report_id: null,
    resume_id: 501,
    reviewed_job_profile: reviewedJobProfile,
    reviewed_job_text:
      "Role A requires Python engineers to build reliable application services and tests.",
    role: "Role A",
    score_status: null,
    scoring_version: null,
    source_content_hash: "a".repeat(64),
    source_type: "pasted_text",
    status: "reviewed",
    updated_at: "2026-07-11T08:01:00Z"
  };
  const applicationB = {
    ...applicationA,
    company: "Role B Company",
    id: 202,
    job_id: 202,
    resume_id: 502,
    role: "Role B",
    source_content_hash: "b".repeat(64)
  };
  let operationApplicationId = applicationB.id;
  let activeLookupFails = false;

  await page.route("**/api/operations/active*", async (route) => {
    if (activeLookupFails) {
      await route.fulfill({ json: { detail: "Temporary status failure" }, status: 503 });
      return;
    }
    const requestedApplicationId = new URL(route.request().url()).searchParams.get(
      "application_id"
    );
    const operationMatchesFilter =
      requestedApplicationId === null || Number(requestedApplicationId) === operationApplicationId;
    await route.fulfill({
      body: JSON.stringify({
        items: operationMatchesFilter
          ? [
              {
                ...pendingApprovalOperation(),
                application_id: operationApplicationId
              }
            ]
          : [],
        count: operationMatchesFilter ? 1 : 0
      }),
      contentType: "application/json",
      status: 200
    });
  });
  await page.route("**/api/applications?limit=20", async (route) => {
    await route.fulfill({
      body: JSON.stringify({ items: [applicationA, applicationB], count: 2 }),
      contentType: "application/json",
      status: 200
    });
  });
  await page.route(/\/api\/applications\/101$/, async (route) => {
    await route.fulfill({ json: applicationA, status: 200 });
  });
  await page.route(/\/api\/applications\/202$/, async (route) => {
    await route.fulfill({ json: applicationB, status: 200 });
  });
  await page.route(/\/api\/resumes\/501$/, async (route) => {
    await route.fulfill({
      json: {
        candidate: {
          email: null,
          links: [],
          location: null,
          name: "Candidate A",
          phone: null
        },
        certifications: [],
        education: [],
        experience: [],
        facts: [],
        projects: [],
        resume_id: 501,
        skills: [],
        warnings: []
      },
      status: 200
    });
  });
  await page.route(/\/api\/resumes\/502$/, async (route) => {
    await route.fulfill({
      json: {
        candidate: {
          email: null,
          links: [],
          location: null,
          name: "Candidate B",
          phone: null
        },
        certifications: [],
        education: [],
        experience: [],
        facts: [],
        projects: [],
        resume_id: 502,
        skills: [],
        warnings: []
      },
      status: 200
    });
  });

  await page.goto(WORKFLOW_PATH);
  await expect(page).toHaveURL("/app/applications/202");
  await expect(page.getByRole("heading", { name: "Role B", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve live draft" })).toBeVisible();

  await page.goto("/app/applications/101");
  await expect(page.getByRole("heading", { name: "Role A", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "AI services" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve live draft" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Run AI analysis" })).toBeEnabled();

  await page.reload();
  await expect(page.getByRole("button", { name: "Approve live draft" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Run AI analysis" })).toBeEnabled();

  activeLookupFails = true;
  await page.reload();
  await expect(page.getByText(/Active analyses could not be verified/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Run AI analysis" })).toBeDisabled();

  activeLookupFails = false;
  operationApplicationId = applicationA.id;
  await page.reload();
  await expect(page.getByRole("heading", { name: "Review the validated live draft" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve live draft" })).toBeVisible();

  let approvalOperationId: string | null = null;
  await page.route("**/api/operations/*/approval", async (route) => {
    approvalOperationId = route.request().url().match(/operations\/([^/]+)\/approval/)?.[1] ?? null;
    await route.fulfill({
      json: { detail: "Approval fixture stopped after verifying operation ownership." },
      status: 503
    });
  });
  await page.getByRole("button", { name: "Approve live draft" }).click();
  await expect.poll(() => approvalOperationId).toBe(pendingApprovalOperation().id);
});

test("application controls stay locked until every protected route dependency hydrates", async ({
  page
}) => {
  const applicationId = 303;
  const resumeId = 503;
  const reportId = 703;
  const reviewedJobProfile = {
    benefits: [],
    company: "Hydration Labs",
    employment_type: null,
    experience_level: null,
    job_id: 303,
    keywords: ["Python"],
    location: null,
    preferred_skills: [],
    required_skills: [],
    responsibilities: ["Keep protected workflows reliable."],
    role_title: "Platform Engineer",
    unclear_items: [],
    warnings: []
  };
  const application = {
    analysis_id: reportId,
    company: "Hydration Labs",
    created_at: "2026-07-11T08:00:00Z",
    id: applicationId,
    job_id: 303,
    job_url: null,
    match_score: 82,
    report_id: reportId,
    resume_id: resumeId,
    reviewed_job_profile: reviewedJobProfile,
    reviewed_job_text:
      "Hydration Labs needs a Python platform engineer to keep protected workflows reliable.",
    role: "Platform Engineer",
    score_status: "scored",
    scoring_version: "evidence_v2",
    source_content_hash: "c".repeat(64),
    source_type: "pasted_text",
    status: "analyzed",
    updated_at: "2026-07-11T08:01:00Z"
  };
  const report = {
    analysis_id: reportId,
    ats_keywords: [],
    cover_letter: "Evidence-backed cover letter.",
    executive_summary: "Evidence-backed report.",
    interview_questions: [],
    job_id: 303,
    match_score: 82,
    matched_skills: [],
    missing_skills: [],
    next_actions: [],
    resume_id: resumeId,
    score_status: "scored",
    scoring_version: "evidence_v2",
    tailored_bullets: [],
    validation_warnings: [],
    weak_skills: []
  };
  let failingDependency: "detail" | "report" | "resume" | null = "detail";

  await page.route("**/api/operations/active*", async (route) => {
    await route.fulfill({
      json: {
        count: 1,
        items: [{ ...pendingApprovalOperation(), application_id: applicationId }]
      },
      status: 200
    });
  });
  await page.route("**/api/applications?limit=20", async (route) => {
    await route.fulfill({ json: { count: 1, items: [application] }, status: 200 });
  });
  await page.route(new RegExp(`/api/applications/${applicationId}$`), async (route) => {
    if (failingDependency === "detail") {
      await route.fulfill({ json: { detail: "Application detail is unavailable." }, status: 503 });
      return;
    }
    await route.fulfill({ json: application, status: 200 });
  });
  await page.route(new RegExp(`/api/resumes/${resumeId}$`), async (route) => {
    if (failingDependency === "resume") {
      await route.fulfill({ json: { detail: "Resume evidence is unavailable." }, status: 503 });
      return;
    }
    await route.fulfill({
      json: {
        candidate: {
          email: null,
          links: [],
          location: null,
          name: "Hydration Candidate",
          phone: null
        },
        certifications: [],
        education: [],
        experience: [],
        facts: [],
        projects: [],
        resume_id: resumeId,
        skills: [],
        warnings: []
      },
      status: 200
    });
  });
  await page.route(new RegExp(`/api/reports/${reportId}$`), async (route) => {
    if (failingDependency === "report") {
      await route.fulfill({ json: { detail: "Report evidence is unavailable." }, status: 503 });
      return;
    }
    await route.fulfill({ json: report, status: 200 });
  });
  await page.route(new RegExp(`/api/reports/${reportId}/workflow$`), async (route) => {
    await route.fulfill({ json: { trace: null }, status: 200 });
  });

  await page.goto(`/app/applications/${applicationId}`);
  await expect(page.getByRole("heading", { name: "Workspace verification required" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve live draft" })).toHaveCount(0);

  for (const dependency of ["resume", "report"] as const) {
    failingDependency = dependency;
    await page.getByRole("button", { name: "Refresh workspace status" }).click();
    await expect(page.getByRole("heading", { name: "Workspace verification required" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve live draft" })).toHaveCount(0);
  }

  failingDependency = null;
  await page.getByRole("button", { name: "Refresh workspace status" }).click();
  await expect(page.getByRole("heading", { name: "Review the validated live draft" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve live draft" })).toBeVisible();
});

test("completed case overview fails closed for unverified draft and historical provenance", async ({
  page
}) => {
  const applicationId = 404;
  const reportId = 804;
  const analysisId = 904;
  const resumeId = 604;
  let releaseDraftLookup!: () => void;
  const draftLookupGate = new Promise<void>((resolve) => {
    releaseDraftLookup = resolve;
  });
  const application = {
    analysis_id: analysisId,
    company: "Archive Labs",
    created_at: "2026-07-01T08:00:00Z",
    id: applicationId,
    job_id: 404,
    job_url: null,
    match_score: 91,
    report_id: reportId,
    resume_id: resumeId,
    reviewed_job_profile: {
      benefits: [],
      company: "Archive Labs",
      employment_type: null,
      experience_level: null,
      job_id: 404,
      keywords: ["Python"],
      location: null,
      preferred_skills: [],
      required_skills: [],
      responsibilities: ["Maintain a verified archive."],
      role_title: "Archive Engineer",
      unclear_items: [],
      warnings: []
    },
    reviewed_job_text: "Archive Labs needs an engineer to maintain a verified archive.",
    role: "Archive Engineer",
    score_status: "provisional",
    scoring_version: "legacy_unversioned",
    source_content_hash: "d".repeat(64),
    source_type: "pasted_text",
    status: "analyzed",
    updated_at: "2026-07-01T08:01:00Z"
  };
  const report = {
    analysis_id: analysisId,
    ats_keywords: [],
    cover_letter: "Historical evidence-backed cover letter.",
    executive_summary: "A historical report whose approval data must be verified separately.",
    interview_questions: [],
    job_id: 404,
    match_score: 91,
    matched_skills: [],
    missing_skills: [],
    next_actions: [],
    resume_id: resumeId,
    score_status: "provisional",
    scoring_version: "legacy_unversioned",
    tailored_bullets: [{ bullet: "Historical suggestion", evidence_ids: [], jd_keywords_used: [], unsupported_claims: [] }],
    validation_status: "block",
    validation_warnings: [
      {
        code: "historical_claim_blocked",
        evidence_ids: [],
        message: "Historical claim needs review.",
        severity: "block"
      }
    ],
    weak_skills: []
  };

  await page.route("**/api/operations/active*", async (route) => {
    await route.fulfill({ json: { count: 0, items: [] }, status: 200 });
  });
  await page.route("**/api/applications?limit=20", async (route) => {
    await route.fulfill({ json: { count: 0, items: [] }, status: 200 });
  });
  await page.route(new RegExp(`/api/applications/${applicationId}$`), async (route) => {
    await route.fulfill({ json: application, status: 200 });
  });
  await page.route(new RegExp(`/api/resumes/${resumeId}$`), async (route) => {
    await route.fulfill({
      json: {
        candidate: {
          email: null,
          links: [],
          location: null,
          name: "Archive Candidate",
          phone: null
        },
        certifications: [],
        education: [],
        experience: [],
        facts: [],
        projects: [],
        resume_id: resumeId,
        skills: [],
        warnings: []
      },
      status: 200
    });
  });
  await page.route(new RegExp(`/api/reports/${reportId}$`), async (route) => {
    await route.fulfill({ json: report, status: 200 });
  });
  await page.route(new RegExp(`/api/reports/${reportId}/workflow$`), async (route) => {
    await route.fulfill({ json: { trace: null }, status: 200 });
  });
  await page.route(
    new RegExp(`/api/applications/${applicationId}/tailored-resume$`),
    async (route) => {
      await draftLookupGate;
      await route.fulfill({ json: { detail: "Draft ownership could not be verified." }, status: 503 });
    }
  );

  await page.goto(`/app/applications/${applicationId}`);
  await expect(page.getByRole("region", { name: "Application case overview" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Provisional legacy score" })).toBeVisible();
  await expect(
    page.getByTestId("case-score").getByText("Validation blocked", { exact: true })
  ).toBeVisible();
  await expect(page.getByText("Reviewed description", { exact: true })).toBeVisible();
  await expect(page.getByText("Verifying the application draft", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Review tailored resume" })).toHaveCount(0);

  releaseDraftLookup();
  await expect(page.getByText("Draft approval is unavailable", { exact: true })).toBeVisible();
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Review tailored resume" })).toHaveCount(0);
});

test("dashboard demo flow renders report and validates exports", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const { applicationId, reportId } = await completeDashboardDemoFlow(page);

  await expectReportExport(page, `/api/reports/${reportId}/markdown`, {
    contentDisposition: `attachment; filename="resumepilot-report-${reportId}.md"`,
    contentType: "text/plain",
    prefix: "# Job Fit Report"
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
  await expectPdfExport(page, `/api/applications/${applicationId}/tailored-resume/pdf`, {
    contentDisposition: `attachment; filename="resumepilot-application-${applicationId}.pdf"`,
    contentType: "application/pdf",
    prefix: "%PDF-"
  });

  expect(
    await page.evaluate(() => document.documentElement.scrollHeight)
  ).toBeLessThan(3_000);
  await captureDashboardScreenshot(page, testInfo, "dashboard-desktop.png");

  await page.goto(`/app/applications/${applicationId}`);
  await expectApplicationCaseOverview(page);
  const nextActionBounds = await page.getByTestId("case-next-action").boundingBox();
  const scoreBounds = await page.getByTestId("case-score").boundingBox();
  expect(nextActionBounds).not.toBeNull();
  expect(scoreBounds).not.toBeNull();
  expect(Math.abs((nextActionBounds?.y ?? 0) - (scoreBounds?.y ?? 0))).toBeLessThan(4);
  expect((nextActionBounds?.x ?? 0) + (nextActionBounds?.width ?? 0)).toBeLessThanOrEqual(
    scoreBounds?.x ?? 0
  );

  const caseAccessibilityScan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    caseAccessibilityScan.violations.map((violation) => violation.id),
    JSON.stringify(caseAccessibilityScan.violations, null, 2)
  ).toEqual([]);
  await captureDashboardScreenshot(page, testInfo, "application-case-bento-desktop.png");

  await page.getByRole("link", { name: "Open full evidence report" }).click();
  await expect(page).toHaveURL(`/app/applications/${applicationId}/report`);
  await expect(page.getByRole("heading", { name: "Evidence-backed fit" })).toBeVisible();
});

test("dashboard demo flow remains usable on mobile", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 1200 });
  const { applicationId } = await completeDashboardDemoFlow(page);

  await expect(page.getByRole("button", { name: "Download Markdown" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download DOCX" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Download LaTeX" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Download PDF" })).toHaveCount(0);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
  ).toBe(true);
  await captureDashboardScreenshot(page, testInfo, "dashboard-mobile-score.png");

  await page.setViewportSize({ width: 320, height: 1200 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
  ).toBe(true);
  await captureDashboardScreenshot(page, testInfo, "dashboard-mobile-320-score.png");

  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect
    .poll(() =>
      page
        .getByRole("button", { name: "Download Markdown" })
        .evaluate((element) => window.getComputedStyle(element).color)
    )
    .toBe("rgb(241, 244, 233)");
  const darkReportAccessibilityScan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    darkReportAccessibilityScan.violations.map((violation) => violation.id),
    JSON.stringify(darkReportAccessibilityScan.violations, null, 2)
  ).toEqual([]);

  for (const testId of [
    "score-method-disclosure",
    "skill-evidence-disclosure",
    "resume-recommendations-disclosure",
    "application-materials-disclosure"
  ]) {
    await page.getByTestId(testId).locator("summary").first().click();
  }
  const mobileMaterials = page.getByTestId("application-materials-disclosure");
  await mobileMaterials.getByText("Read full cover letter", { exact: true }).click();
  const mobileInterviewPanel = mobileMaterials.locator("section").filter({
    has: page.getByRole("heading", { name: "Interview preparation" })
  });
  await mobileInterviewPanel.locator("details > summary").first().click();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
  ).toBe(true);
  await captureDashboardScreenshot(page, testInfo, "dashboard-mobile-320-report-expanded.png");

  const unbrokenToken = "schemaUnboundedReportToken".repeat(12);
  for (const label of [
    "Python, matched",
    "Observability, preferred",
    "Distributed tracing, add only if true"
  ]) {
    await page
      .getByRole("region", { name: "Report at a glance" })
      .getByLabel(label)
      .evaluate((element, token) => {
        const nestedLabel = element.querySelector("span");
        (nestedLabel ?? element).textContent = token;
      }, unbrokenToken);
  }
  const expandedLedgerValues = [
    page.getByTestId("skill-evidence-disclosure").locator("h5").first(),
    page.getByTestId("skill-evidence-disclosure").locator("h5").last(),
    page.getByTestId("resume-recommendations-disclosure").locator("h5").first(),
    mobileInterviewPanel.locator("h4").first()
  ];
  for (const value of expandedLedgerValues) {
    await value.evaluate((element, token) => {
      element.textContent = token;
    }, unbrokenToken);
    expect(
      await value.evaluate((element) => ({
        contained: element.scrollWidth <= element.clientWidth,
        overflowWrap: window.getComputedStyle(element).overflowWrap
      }))
    ).toEqual({ contained: true, overflowWrap: "anywhere" });
  }
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
  ).toBe(true);

  await page.goto(`/app/applications/${applicationId}`);
  await expectApplicationCaseOverview(page);
  const mobileNextActionBounds = await page.getByTestId("case-next-action").boundingBox();
  const mobileScoreBounds = await page.getByTestId("case-score").boundingBox();
  expect(mobileNextActionBounds).not.toBeNull();
  expect(mobileScoreBounds).not.toBeNull();
  expect(mobileScoreBounds?.y ?? 0).toBeGreaterThan(
    (mobileNextActionBounds?.y ?? 0) + (mobileNextActionBounds?.height ?? 0)
  );
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
  ).toBe(true);
  await captureDashboardScreenshot(page, testInfo, "application-case-bento-mobile-320.png");

  await page.getByRole("link", { name: "Review tailored resume" }).click();
  await expect(page).toHaveURL(/\/app\/applications\/\d+\/resume$/);
  await expect(page.getByRole("button", { name: "Download DOCX" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download LaTeX" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download PDF" })).toBeVisible();

  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
  ).toBe(true);
  await captureDashboardScreenshot(page, testInfo, "dashboard-mobile-320-draft.png");
});

async function expectApplicationCaseOverview(page: Page): Promise<void> {
  await expect(page.getByRole("region", { name: "Application case overview" })).toBeVisible({
    timeout: 20_000
  });
  await expect(page.getByRole("heading", { name: "Evidence-fit score" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence snapshot" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Every gate stays visible" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Fit report" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Tailored resume" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open full evidence report" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Review tailored resume" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence-backed fit" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Cover letter draft" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Interview preparation" })).toHaveCount(0);
}

test("dashboard sends a job posting URL analysis request", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto(WORKFLOW_PATH);

  const jobUrl = "https://example.com/jobs/backend-engineer";
  await page.route("**/api/jobs/preview", async (route) => {
    await route.fulfill({
      body: JSON.stringify({
        job_url: jobUrl,
        reviewed_job_text:
          "Backend Engineer at Example Co. Required Python experience. Build backend services and reliable APIs.",
        source_content_hash: "url-preview-hash",
        source_type: "url",
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
  expect(capturedPayloads[0]?.application_id).toEqual(expect.any(Number));
  expect(capturedPayloads[0]?.job_url).toBeUndefined();
  expect(capturedPayloads[0]?.job_text).toBeUndefined();
  expect(capturedPayloads[0]?.reviewed_job_profile).toBeUndefined();
});

test("pasted job evidence persists and reopens before analysis", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  const jobText = [
    "Pasted Recovery Engineer",
    "Company: Restore Labs",
    "Required Python and FastAPI experience.",
    "Build reliable APIs and write automated tests for recovery workflows."
  ].join("\n");
  const previewPayloads: Record<string, unknown>[] = [];

  await page.route("**/api/jobs/preview", async (route) => {
    previewPayloads.push(
      JSON.parse(route.request().postData() ?? "{}") as Record<string, unknown>
    );
    await route.fulfill({
      body: JSON.stringify({
        job_url: null,
        parser: "pasted_text",
        profile: {
          benefits: [],
          company: "Restore Labs",
          employment_type: null,
          experience_level: null,
          job_id: 0,
          keywords: ["Python", "FastAPI"],
          location: null,
          preferred_skills: [],
          required_skills: [
            {
              confidence: "high",
              evidence_text: "Required Python experience.",
              id: "job_required_001",
              importance: "required",
              name: "Python"
            },
            {
              confidence: "high",
              evidence_text: "Required FastAPI experience.",
              id: "job_required_002",
              importance: "required",
              name: "FastAPI"
            }
          ],
          responsibilities: [
            "Build reliable APIs and write automated tests for recovery workflows."
          ],
          role_title: "Pasted Recovery Engineer",
          unclear_items: [],
          warnings: []
        },
        quality_checks: [
          {
            code: "required_or_preferred_skills",
            message: "Required skills were extracted from pasted text.",
            status: "pass"
          }
        ],
        raw_text_char_count: jobText.length,
        reviewed_job_text: jobText,
        source_content_hash: "pasted-recovery-hash",
        source_type: "pasted_text",
        status: "ready"
      }),
      contentType: "application/json",
      status: 200
    });
  });

  await page.goto(WORKFLOW_PATH);
  await page.getByRole("radio", { name: /Paste description/ }).check();
  await page.getByRole("textbox", { name: "Job description" }).fill(jobText);
  await expect(page.getByText(`${jobText.length.toLocaleString()} / 50,000`)).toBeVisible();
  await page.getByRole("button", { name: "Review job evidence" }).click();
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByRole("heading", { name: "Resume upload" })).toBeVisible();
  expect(previewPayloads[0]).toEqual({ job_text: jobText });

  await page.goto("/app/applications");
  const savedApplication = page
    .getByRole("article")
    .filter({ hasText: "Pasted Recovery Engineer" })
    .first();
  await expect(savedApplication).toBeVisible();
  await savedApplication.getByRole("button", { name: "Open" }).click();
  await expect(page).toHaveURL(/\/app\/applications\/\d+$/);
  await expect(page.getByRole("heading", { name: "Resume upload" })).toBeVisible();
  await expect(page.getByText("Text added", { exact: true })).toBeVisible();

  await uploadResume(page);
  const analysisPayloads: Record<string, unknown>[] = [];
  await page.route("**/api/jobs/analyze", async (route) => {
    analysisPayloads.push(
      JSON.parse(route.request().postData() ?? "{}") as Record<string, unknown>
    );
    await route.fulfill({
      body: JSON.stringify({ detail: "mocked pasted analysis request" }),
      contentType: "application/json",
      status: 400
    });
  });
  await page.getByRole("button", { name: "Run AI analysis" }).click();
  await expect(page.getByText("mocked pasted analysis request")).toBeVisible();
  expect(analysisPayloads[0]?.application_id).toEqual(expect.any(Number));
  expect(analysisPayloads[0]?.job_url).toBeUndefined();
  expect(analysisPayloads[0]?.job_text).toBeUndefined();
});

test("blocked job URLs require pasted source text", async ({ page }) => {
  const blockedUrl = "https://example.com/jobs/private-role";
  await page.route("**/api/jobs/preview", async (route) => {
    await route.fulfill({
      body: JSON.stringify({
        job_url: blockedUrl,
        parser: "generic_html",
        profile: {
          benefits: [],
          company: null,
          employment_type: null,
          experience_level: null,
          job_id: 0,
          keywords: [],
          location: null,
          preferred_skills: [],
          required_skills: [],
          responsibilities: [],
          role_title: null,
          unclear_items: [],
          warnings: []
        },
        quality_checks: [
          {
            code: "blocked_private",
            message: "This listing is private or blocked. Paste the description instead.",
            status: "fail"
          }
        ],
        raw_text_char_count: 0,
        reviewed_job_text: "",
        source_content_hash: null,
        source_type: "url",
        status: "blocked_private"
      }),
      contentType: "application/json",
      status: 200
    });
  });

  await page.goto(WORKFLOW_PATH);
  await page.getByRole("textbox", { name: "Job listing URL" }).fill(blockedUrl);
  await page.getByRole("button", { name: "Review job evidence" }).click();
  await expect(page.getByText("Job listing could not be reviewed")).toBeVisible();
  await expect(page.getByRole("button", { name: "Source text required" })).toBeDisabled();
  await page.getByRole("button", { name: "Paste job description instead" }).click();
  await expect(page.getByRole("textbox", { name: "Job description" })).toBeVisible();
});

test("dashboard flags unclear job requirement extraction", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await mockFixtureJobPreviews(page);
  await page.goto(WORKFLOW_PATH);

  await page.getByRole("textbox", { name: "Job listing URL" }).fill(
    jobPostingUrl(page, UNCLEAR_JOB_POSTING_PATH)
  );
  await page.getByRole("button", { name: "Review job evidence" }).click();
  await expect(page.getByRole("heading", { name: "Review job evidence" })).toBeVisible();
  await expect(page.getByText("Job evidence needs review")).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with warning" })).toBeVisible();
  await page.getByRole("button", { name: "Continue with warning" }).click();
  await uploadResume(page);
  await runAiAnalysis(page, { expectDraftComparison: false });

  await expect(
    page.getByText("Provisional evidence-fit score", { exact: true })
  ).toBeVisible();
  await expect(page.getByText("Needs job details", { exact: true })).toBeVisible();
  await expect(page.getByText("Job details need review", { exact: true })).toBeVisible();
  const reportAtGlance = page.getByRole("region", { name: "Report at a glance" });
  await expect(
    reportAtGlance.getByText("No evidence-backed matches yet", { exact: true })
  ).toBeVisible();
  await expect(reportAtGlance.getByText("Gaps not available", { exact: true })).toBeVisible();
  await expect(
    reportAtGlance.getByText("No ATS keywords extracted", { exact: true })
  ).toBeVisible();
});

test("dashboard labels and preserves a legacy report without a score breakdown", async ({
  page
}) => {
  await mockFixtureJobPreviews(page);
  await page.goto(WORKFLOW_PATH);
  await enterJobListing(page, { url: jobPostingUrl(page, SAMPLE_JOB_POSTING_PATH) });
  await uploadResume(page);
  await page.route(/\/api\/reports\/\d+$/, async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.scoring_version = "legacy_unversioned";
    payload.score_status = "scored";
    payload.score_breakdown = null;
    await route.fulfill({ json: payload, response });
  });

  await runAiAnalysis(page, { expectDraftComparison: false });

  await expect(page.getByText("Legacy unversioned score", { exact: true })).toBeVisible();
  await expect(page.getByText("Legacy score", { exact: true })).toBeVisible();
  await expect(page.getByText("Historical score", { exact: true }).first()).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "About this historical score" })
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "How this evidence-fit score is calculated" })
  ).toHaveCount(0);
  await page.getByTestId("score-method-disclosure").locator("summary").first().click();
  await expect(
    page.getByText(
      "Detailed evidence components were not recorded for this historical report. " +
        "Re-running creates a new report whose score may differ; this saved report remains unchanged."
    )
  ).toBeVisible();
});

test("tailored resume explains blocked unsupported edits inline", async ({ page }) => {
  await mockFixtureJobPreviews(page);
  await page.goto(WORKFLOW_PATH);
  await enterJobListing(page, { url: jobPostingUrl(page, SAMPLE_JOB_POSTING_PATH) });
  await uploadResume(page);
  await page.getByRole("button", { name: "Run AI analysis" }).click();
  await expect(page.getByRole("heading", { name: "Evidence-backed fit" })).toBeVisible({
    timeout: 30_000
  });
  await expect(page.getByRole("heading", { name: "Tailored resume workspace" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Review tailored resume" })).toBeVisible();
  await page.getByRole("button", { name: "Review tailored resume" }).click();
  await expect(page.getByRole("heading", { name: "Tailored resume workspace" })).toBeVisible();

  const draftWorkspace = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Tailored resume workspace" })
  });
  const editor = draftWorkspace.getByRole("textbox", { name: /Edit tailored bullet/ }).first();
  await editor.fill(`${await editor.inputValue()} Used Kubernetes with 99% reliability.`);
  await page.route("**/api/applications/*/tailored-resume/items/*", async (route) => {
    await route.fulfill({
      body: JSON.stringify({
        detail: {
          message: "Accepted resume bullet must be supported by linked evidence.",
          warnings: [
            {
              code: "draft_bullet_has_unsupported_skill",
              evidence_ids: ["projects_001"],
              message: "Kubernetes is not present in the linked resume evidence.",
              severity: "block"
            },
            {
              code: "draft_bullet_has_unsupported_claim",
              evidence_ids: ["projects_001"],
              message: "99% reliability is not present in the linked resume evidence.",
              severity: "block"
            }
          ]
        }
      }),
      contentType: "application/json",
      status: 422
    });
  });

  await draftWorkspace.getByRole("button", { name: "Accept" }).first().click();
  await expect(draftWorkspace.getByText("Change blocked")).toBeVisible();
  await expect(
    draftWorkspace.getByText("Kubernetes is not present in the linked resume evidence.")
  ).toBeVisible();
  await expect(
    draftWorkspace.getByText("99% reliability is not present in the linked resume evidence.")
  ).toBeVisible();
});

test("standalone report disables tailoring without an application route", async ({ page }) => {
  await mockFixtureJobPreviews(page);
  await page.goto(WORKFLOW_PATH);

  await enterJobListing(page, { url: jobPostingUrl(page, SAMPLE_JOB_POSTING_PATH) });
  await uploadResume(page);
  await page.getByRole("button", { name: "Run AI analysis" }).click();

  await expect(page.getByRole("heading", { name: "Evidence-backed fit" })).toBeVisible({
    timeout: 30_000
  });
  const reportLabel = await page.getByText(/^Report \d+$/).first().textContent();
  const reportId = reportLabel?.match(/\d+/)?.[0];
  if (!reportId) {
    throw new Error(`Could not parse the report id from: ${reportLabel ?? "missing label"}`);
  }
  await page.goto(`/app/reports/${reportId}`);
  await expect(page.getByRole("heading", { name: "Evidence-backed fit" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Review tailored resume" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Review tailored resume" })).toHaveAttribute(
    "title",
    "Tailoring is unavailable because this report is not linked to an application."
  );
});

test("report ledger reopens the selected saved report accurately", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await mockFixtureJobPreviews(page);
  await page.goto(WORKFLOW_PATH);

  await enterJobListing(page, {
    url: jobPostingUrl(page, BACKEND_PLATFORM_JOB_PATH)
  });
  await uploadResume(page);
  const firstReportId = (await runAiAnalysis(page)).reportId;

  await page.route("**/api/reports?limit=20", async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    const historical = payload.items.find(
      (item: { report_id: number }) => item.report_id === Number(firstReportId)
    );
    if (historical) {
      historical.scoring_version = "deterministic_v1";
      historical.score_status = "scored";
    }
    await route.fulfill({ json: payload, response });
  });
  await page.route("**/api/applications?limit=20", async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    const historical = payload.items.find(
      (item: { report_id: number | null }) => item.report_id === Number(firstReportId)
    );
    if (historical) {
      historical.scoring_version = "deterministic_v1";
      historical.score_status = "scored";
    }
    await route.fulfill({ json: payload, response });
  });

  await page.goto(WORKFLOW_PATH);
  const secondReportId = await analyzeJob(page, {
    url: jobPostingUrl(page, DATA_API_JOB_PATH)
  });

  expect(secondReportId).not.toBe(firstReportId);

  await page.route(new RegExp(`/api/reports/${firstReportId}$`), async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.scoring_version = "deterministic_v1";
    payload.score_status = "scored";
    payload.score_breakdown = null;
    await route.fulfill({ json: payload, response });
  });

  await page.goto("/app/reports");
  await expect(page.getByRole("heading", { name: "Reports", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Data API Engineer/ })).toBeVisible();
  await page.getByRole("button", { name: /Backend Platform Engineer/ }).click();
  await expect(page).toHaveURL(`/app/reports/${firstReportId}`);
  await expect(page.getByRole("heading", { name: "Evidence-backed fit" })).toBeVisible();
  await expect(page.getByText("Deterministic v1 score", { exact: true })).toBeVisible();
  await expect(page.getByText("Historical score", { exact: true }).first()).toBeVisible();
  const exportResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/api/reports/${firstReportId}/markdown`)
  );
  await page.getByRole("button", { name: "Download Markdown" }).click();
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

async function installExpandedReportFixture(page: Page): Promise<void> {
  await page.route(/\/api\/reports\/\d+$/, async (route) => {
    const response = await route.fetch();
    const report = (await response.json()) as ApplicationReport;

    while (report.matched_skills.length < 10) {
      const index = report.matched_skills.length + 1;
      report.matched_skills.push({
        confidence: "high",
        job_evidence_text: `Overflow skill ${index} is required by the reviewed job evidence.`,
        match_type: "exact",
        resume_evidence_ids: ["projects_001"],
        skill: `Overflow skill ${index}`
      });
    }
    if (!report.matched_skills.some((item) => item.skill === "Overflow skill 10")) {
      report.matched_skills.push({
        confidence: "high",
        job_evidence_text: "Overflow skill 10 is required by the reviewed job evidence.",
        match_type: "exact",
        resume_evidence_ids: ["projects_001"],
        skill: "Overflow skill 10"
      });
    }
    if (!report.missing_skills.some((item) => item.importance === "preferred")) {
      report.missing_skills.unshift({
        importance: "preferred",
        job_evidence_text: "Observability is preferred for this role.",
        recommendation: "Add observability only when supported by truthful project evidence.",
        skill: "Observability",
        why_it_matters: "The reviewed job evidence marks this capability as preferred."
      });
    }
    if (report.weak_skills.length === 0) {
      report.weak_skills.push({
        reason: "The resume mentions ownership without a concrete project or work example.",
        resume_evidence_ids: ["summary_001"],
        skill: "Production ownership"
      });
    }
    while (report.missing_skills.length < 6) {
      const index = report.missing_skills.length + 1;
      report.missing_skills.push({
        importance: "required",
        job_evidence_text: `Overflow gap ${index} is required by the role.`,
        recommendation: `Prepare truthful evidence for overflow gap ${index}.`,
        skill: `Overflow gap ${index}`,
        why_it_matters: "The reviewed job evidence marks this capability as required."
      });
    }
    if (!report.missing_skills.some((item) => item.skill === "Overflow gap 6")) {
      report.missing_skills.push({
        importance: "required",
        job_evidence_text: "Overflow gap 6 is required by the role.",
        recommendation: "Prepare truthful evidence for overflow gap 6.",
        skill: "Overflow gap 6",
        why_it_matters: "The reviewed job evidence marks this capability as required."
      });
    }
    if (!report.ats_keywords.some((item) => item.status === "add_only_if_true")) {
      report.ats_keywords.unshift({
        evidence_ids: [],
        keyword: "Distributed tracing",
        note: "Add only if the resume can link this phrase to truthful delivery evidence.",
        status: "add_only_if_true"
      });
    }
    while (report.ats_keywords.length < 12) {
      const index = report.ats_keywords.length + 1;
      report.ats_keywords.push({
        evidence_ids: ["projects_001"],
        keyword: `Overflow keyword ${index}`,
        note: "Supported by linked project evidence.",
        status: "supported"
      });
    }
    if (!report.ats_keywords.some((item) => item.keyword === "Overflow keyword 12")) {
      report.ats_keywords.push({
        evidence_ids: ["projects_001"],
        keyword: "Overflow keyword 12",
        note: "Supported by linked project evidence.",
        status: "supported"
      });
    }
    while (report.next_actions.length < 6) {
      const index = report.next_actions.length + 1;
      report.next_actions.push(`Overflow next action ${index}.`);
    }
    if (!report.next_actions.includes("Overflow next action 6.")) {
      report.next_actions.push("Overflow next action 6.");
    }

    await route.fulfill({ json: report, response });
  });
}

async function completeDashboardDemoFlow(page: Page): Promise<CompletedDashboardFlow> {
  await mockFixtureJobPreviews(page);
  await page.goto(WORKFLOW_PATH);
  await expect(page.getByRole("heading", { name: "Guided application workflow" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Application workflow" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Job listing" })).toBeVisible();

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

  await page.getByLabel("Resume file").setInputFiles(RESUME_FIXTURE);
  await expect(page.getByText("backend_fresher.md")).toBeVisible();

  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByRole("heading", { name: "AI services" })).toBeVisible();
  await expect(page.getByText("Parse job evidence")).toBeVisible();

  await page.getByText("Review parsed resume evidence", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "Resume extraction" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Parsed skills" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence ledger" })).toBeVisible();
  await page.getByText("Review parsed resume evidence", { exact: true }).click();

  await installExpandedReportFixture(page);
  const result = await runAiAnalysis(page, { acceptFirstDraft: true });

  await expect(page.getByText("Evidence-fit score", { exact: true })).toBeVisible();
  await expect(
    page.getByText("This deterministic comparison is not a hiring probability or ATS guarantee.")
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "How this evidence-fit score is calculated" })
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Matched skills" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Missing or weak" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ATS keywords" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Next actions" })).toBeVisible();
  const reportAtGlance = page.getByRole("region", { name: "Report at a glance" });
  await expect(reportAtGlance.getByLabel("Observability, preferred")).toBeVisible();
  await expect(reportAtGlance.getByLabel("Production ownership, weak evidence")).toBeVisible();
  await expect(reportAtGlance.getByLabel("Distributed tracing, add only if true")).toBeVisible();
  await expect(page.getByText(/Validation: (Passed|Needs review|Blocked)/)).toBeVisible();
  const openCoverLetterButton = page.getByRole("button", { name: "Open cover letter" });
  await expect(openCoverLetterButton).toBeVisible();
  await expect(page.getByRole("button", { name: "Download DOCX" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Workflow trace" })).toBeVisible();
  await expect(page.getByText(/Report \d+/).first()).toBeVisible();
  await expect(page.getByText("Deterministic fallback", { exact: true })).toBeVisible();
  await expect(page.getByText(/\d+(?:\.\d)? (?:ms|s) total/)).toBeVisible();
  await expect(page.getByText("Overflow skill 10", { exact: true })).not.toBeVisible();
  await expect(page.getByText("Overflow keyword 12", { exact: true })).not.toBeVisible();

  const collapsedReportAccessibilityScan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    collapsedReportAccessibilityScan.violations.map((violation) => violation.id),
    JSON.stringify(collapsedReportAccessibilityScan.violations, null, 2)
  ).toEqual([]);

  const scoreDisclosure = page.getByTestId("score-method-disclosure");
  const scoreSummary = scoreDisclosure.locator("summary").first();
  await expect(scoreDisclosure).not.toHaveAttribute("open", "");
  await scoreSummary.focus();
  await page.keyboard.press("Enter");
  await expect(scoreDisclosure).toHaveAttribute("open", "");
  await expect(scoreSummary).toBeFocused();
  await expect(page.getByText("Required skill evidence", { exact: true })).toBeVisible();
  await expect(page.getByText("Preferred skill evidence", { exact: true })).toBeVisible();
  await expect(page.getByText("Work/project proof", { exact: true })).toBeVisible();
  await expect(
    scoreDisclosure.getByText(
      /\d+ backed by work\/projects · \d+ from other resume sections · Does not change the fit score/
    )
  ).toBeVisible();
  await expect(
    page.getByRole("progressbar", { name: "Work/project proof score" })
  ).toHaveCount(0);
  await expect(
    page.getByRole("progressbar", { name: "Required skill evidence score" })
  ).toBeVisible();
  await scoreDisclosure.getByText(/View calculation and \d+ linked/).first().click();
  await expect(scoreDisclosure.getByLabel(/Resume .* evidence\./).first()).toBeVisible();
  const workProofRow = scoreDisclosure.locator("article").filter({
    has: page.getByText("Work/project proof", { exact: true })
  });
  await workProofRow.getByText(/View explanation and \d+ linked/).click();
  await expect(
    workProofRow.getByText(/this check does not add or remove fit-score points/i)
  ).toBeVisible();

  const skillDisclosure = page.getByTestId("skill-evidence-disclosure");
  const skillSummary = skillDisclosure.locator("summary").first();
  await skillSummary.focus();
  await page.keyboard.press("Space");
  await expect(skillDisclosure).toHaveAttribute("open", "");
  await expect(skillSummary).toBeFocused();
  await expect(skillDisclosure.getByText("Overflow skill 10", { exact: true })).toBeVisible();
  await expect(skillDisclosure.getByText("Overflow gap 6", { exact: true })).toBeVisible();

  const recommendationDisclosure = page.getByTestId("resume-recommendations-disclosure");
  await recommendationDisclosure.locator("summary").first().click();
  await expect(
    recommendationDisclosure.getByText("Overflow keyword 12", { exact: true })
  ).toBeVisible();
  await expect(
    recommendationDisclosure.getByText(/Overflow next action 6\./)
  ).toBeVisible();

  const materialsDisclosure = page.getByTestId("application-materials-disclosure");
  await expect(materialsDisclosure).not.toHaveAttribute("open", "");
  await openCoverLetterButton.click();
  await expect(materialsDisclosure).toHaveAttribute("open", "");
  await expect(page.getByRole("heading", { name: "Cover letter draft" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Interview preparation" })).toBeVisible();
  const coverLetterDisclosure = materialsDisclosure.getByTestId(
    "cover-letter-draft-disclosure"
  );
  await expect(coverLetterDisclosure).toHaveAttribute("open", "");
  await expect(coverLetterDisclosure.locator("summary")).toBeFocused();
  const interviewPanel = materialsDisclosure.locator("section").filter({
    has: page.getByRole("heading", { name: "Interview preparation" })
  });
  await interviewPanel.locator("details > summary").first().click();

  const expandedReportAccessibilityScan = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    expandedReportAccessibilityScan.violations.map((violation) => violation.id),
    JSON.stringify(expandedReportAccessibilityScan.violations, null, 2)
  ).toEqual([]);

  if (!result.applicationId) {
    throw new Error("Accepted draft flow did not expose an application export action.");
  }

  await page.goto("/app/settings");
  await expect(page.getByRole("heading", { name: "Plan usage meter" })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Analysis runs usage" })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Exports usage" })).toBeVisible();

  await page.goto("/app/applications");
  const applicationRow = page
    .getByRole("article")
    .filter({ hasText: "Backend Engineer" })
    .first();
  await expect(applicationRow).toContainText("Report ready");
  await applicationRow.getByRole("button", { name: "Applied" }).click();
  await expect(applicationRow).toContainText("Applied");

  await page.goto(`/app/applications/${result.applicationId}/report`);
  await expect(page.getByRole("heading", { name: "Evidence-backed fit" })).toBeVisible();
  const savedSkillDisclosure = page.getByTestId("skill-evidence-disclosure");
  await savedSkillDisclosure.locator("summary").first().click();
  await savedSkillDisclosure.getByText(/View \d+ linked/).first().click();
  const pageText = await page.locator("body").innerText();
  expect(pageText).not.toMatch(/(?:summary|skills)_\d{3} ·/);
  expect(pageText).toMatch(/(?:Project evidence|Work evidence|Resume summary|Skills section) #\d+/);
  await savedSkillDisclosure.locator("summary").first().click();
  await expect(savedSkillDisclosure).not.toHaveAttribute("open", "");
  await page.evaluate(() => window.scrollTo(0, 0));

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
  await uploadResume(page);
  return (await runAiAnalysis(page)).reportId;
}

async function enterJobListing(page: Page, input: AnalyzeJobInput): Promise<void> {
  await expect(page.getByRole("button", { name: "Refresh workspace status" })).toBeEnabled({
    timeout: 20_000
  });
  const jobUrlInput = page.getByRole("textbox", { name: "Job listing URL" });
  if (!(await jobUrlInput.isVisible().catch(() => false))) {
    await page.getByRole("button", { name: "Edit job listing" }).click();
  }

  await jobUrlInput.fill(input.url);
  const reviewJobEvidenceButton = page.getByRole("button", { name: "Review job evidence" });
  await expect(reviewJobEvidenceButton).toBeEnabled({ timeout: 20_000 });
  await reviewJobEvidenceButton.click();
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
        reviewed_job_text: [
          fixture.role ?? "Role not listed",
          fixture.company ?? "Company not listed",
          ...fixture.requiredSkills.map((skill) => `Required ${skill} experience.`),
          ...fixture.preferredSkills.map((skill) => `Preferred ${skill} experience.`),
          ...fixture.responsibilities
        ].join("\n"),
        source_content_hash: `fixture-${new URL(payload.job_url).pathname}`,
        source_type: "url",
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
  options: { acceptFirstDraft?: boolean; expectDraftComparison?: boolean } = {}
): Promise<RunAiAnalysisResult> {
  await expect(page.getByRole("heading", { name: "AI services" })).toBeVisible();
  await page.getByRole("button", { name: "Run AI analysis" }).click();
  await expect(page.getByRole("heading", { name: "Evidence-backed fit" })).toBeVisible({
    timeout: 30_000
  });
  await expect(page.getByRole("heading", { name: "Tailored resume workspace" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Review tailored resume" })).toBeVisible();

  const reportLabel = await page.getByText(/^Report \d+$/).first().textContent();
  const reportId = reportLabel?.match(/\d+/)?.[0];
  if (!reportId) {
    throw new Error(`Could not parse the active report id from: ${reportLabel ?? "missing label"}`);
  }

  if (!(options.expectDraftComparison ?? true) && !options.acceptFirstDraft) {
    return {
      applicationId: null,
      reportId
    };
  }

  await page.getByRole("button", { name: "Review tailored resume" }).click();
  await expect(page.getByRole("heading", { name: "Tailored resume workspace" })).toBeVisible();

  const draftWorkspace = page.locator("section").filter({
    has: page.getByRole("heading", { name: "Tailored resume workspace" })
  });
  let applicationId: string | null = null;

  if (options.expectDraftComparison ?? true) {
    await expect(draftWorkspace.getByText("Original resume evidence").first()).toBeVisible();
    await expect(draftWorkspace.getByText("Proposed / edited bullet").first()).toBeVisible();
    await expect(draftWorkspace.getByText("Why this change").first()).toBeVisible();
  }

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

async function expectPdfExport(
  page: Page,
  exportPath: string,
  expected: ExpectedExport
): Promise<void> {
  const exportUrl = new URL(exportPath, page.url()).toString();
  const response = await page.request.post(exportUrl, {
    headers: { "idempotency-key": `playwright-pdf-${Date.now()}` }
  });
  expect(response.status(), exportPath).toBe(202);
  let operation = (await response.json()) as {
    id: string;
    status: string;
    error?: { message?: string } | null;
  };
  for (let attempt = 0; attempt < 30 && operation.status !== "succeeded"; attempt += 1) {
    if (["failed", "dead_lettered", "canceled"].includes(operation.status)) {
      throw new Error(operation.error?.message ?? `PDF export ${operation.status}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
    const pollResponse = await page.request.get(
      new URL(`/api/operations/${operation.id}`, page.url()).toString()
    );
    expect(pollResponse.status()).toBe(200);
    operation = await pollResponse.json();
  }
  expect(operation.status).toBe("succeeded");

  const artifactPath = `/api/operations/${operation.id}/artifact`;
  const artifactResponse = await page.request.get(new URL(artifactPath, page.url()).toString());
  expect(artifactResponse.status(), artifactPath).toBe(200);
  expect(artifactResponse.headers()["content-type"], artifactPath).toContain(
    expected.contentType
  );
  expect(artifactResponse.headers()["content-disposition"], artifactPath).toBe(
    expected.contentDisposition
  );
  expect(artifactResponse.headers()["cache-control"], artifactPath).toContain(
    "private, no-store"
  );
  const body = await artifactResponse.body();
  expect(body.subarray(0, expected.prefix.length).toString("latin1"), artifactPath).toBe(
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
