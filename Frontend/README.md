# ResumePilot Frontend

Next.js evidence workspace and public authentication surface for ResumePilot.

## Stack

- Next.js App Router
- React and TypeScript
- Tailwind CSS
- Self-hosted Manrope and IBM Plex Mono typography
- Light/dark product tokens with reduced-motion support
- Restrained Aceternity UI and Magic UI adaptations on public/auth surfaces
- Server route handlers as a backend-for-frontend proxy to FastAPI
- Playwright browser smoke tests

## Authenticated route map

- `/app/dashboard` — portfolio overview, active-operation attention, recent applications, and latest reports.
- `/app/applications` — complete application pipeline and status management.
- `/app/applications/new` — combined job source, evidence review, resume upload, analysis, report, and approval workflow.
- `/app/applications/[applicationId]` — focused application continuation.
- `/app/applications/[applicationId]/report` — application-linked evidence report.
- `/app/applications/[applicationId]/resume` — tailored bullet approval and accepted-draft exports.
- `/app/reports` and `/app/reports/[reportId]` — report ledger and standalone read-only report deep links.
- `/app/settings` — account scope, plan usage, runtime health, OpenClaw integration, and export boundaries.

Every `/app` route is server-gated. The public `/` route remains the product and
authentication entry point, and authenticated root requests redirect to the
workspace dashboard.

## Current workspace capabilities

- Guided workflow: job URL or pasted description, reviewed job evidence, resume
  upload, durable AI analysis, validated report, and tailored resume approval.
- Application pipeline workspace backed by `/api/applications`, with saved reviewed drafts and `reviewed`, `analyzed`, `exported`, and `applied` statuses.
- Job preview through `/api/jobs/preview` so users can inspect and edit extracted role, company, skills, responsibilities, and extraction quality before upload.
- Resume upload through the same-origin `/api/resumes/upload` proxy after the job evidence is reviewed.
- Job analysis through `/api/jobs/analyze` using the saved reviewed source
  snapshot, with operation progress, cancellation, safe failures, and retry-safe
  idempotency. Operation responses carry application provenance, and routed
  approval/cancellation controls reject operations owned by another case file.
  Active recovery uses an application-filtered endpoint and fails closed when
  status cannot be verified; unlinked in-flight work is isolated from intake.
  Saved-route actions also remain locked until application detail, resume
  evidence, and report evidence hydrate successfully, and Refresh retries both
  status and protected route hydration.
- Per-analysis live AI consent for eligible plans; deterministic processing remains the default and provider prompts exclude candidate contact details.
- Tailored resume workspace through `/api/applications/[applicationId]/tailored-resume` where users edit, accept, or reject evidence-backed bullets before final DOCX, LaTeX, or PDF export.
- Report viewing with JSON, Markdown, workflow trace timings/runtime metadata,
  provider token/cost estimates, claim-validation status, cover-letter and
  interview-prep panels, and evidence comparisons. Resume DOCX/LaTeX/PDF
  downloads are available only from the accepted application draft.
- Dedicated application/report portfolio views plus a Settings surface for account/session state, usage limits, OpenClaw Gateway/provider readiness, runtime health, and validation boundaries.
- Branded anonymous, Clerk sign-in/sign-up, loading, error, and not-found states with a shared evidence-desk visual system.
- Theme persistence, system dark-mode support, and purposefully limited motion that is removed for `prefers-reduced-motion` users.

Aceternity's Spotlight and Bento Grid patterns and Magic UI's Blur Fade pattern
are adapted as locally owned components. They are used for public storytelling,
not around approvals, validation, or other critical workflow controls.

## Local setup

```bash
cd Frontend
cp .env.example .env
npm install
npm run dev
```

Default frontend URL:

```text
http://127.0.0.1:3000
```

The dashboard expects FastAPI to be running at `RESUMEPILOT_API_BASE_URL`, defaulting to:

```text
http://127.0.0.1:8002
```

## Browser smoke

Install the Chromium browser once:

```bash
npm run test:e2e:install
```

Run the dashboard browser smoke:

```bash
npm run test:e2e
```

Playwright builds the frontend on every run, starts FastAPI on `127.0.0.1:8040`,
starts a fresh production Next.js server on `127.0.0.1:3040`, captures the sample
job listing URL, verifies the job evidence review gate, uploads the backend
sample resume, runs the AI workflow, verifies the job URL request contract,
checks URL and pasted-description snapshots, application-id analysis operations,
cross-application operation isolation across reloads, progress/cancellation
behavior, dependency-hydration failure and recovery, workflow trace timing,
Markdown report export,
accepted-draft DOCX/LaTeX/PDF exports, application status transitions, security headers, and
the automated WCAG A/AA baseline. The suite also verifies routed Dashboard,
Applications, Reports, Settings, application report, and tailored-resume views,
plus compact 320px dark/reduced-motion behavior, completed report/draft overflow,
and the branded 404 recovery path. It captures
desktop/mobile screenshots under
`Frontend/.local/playwright-results`.

Override ports with `RESUMEPILOT_E2E_BACKEND_PORT` and
`RESUMEPILOT_E2E_FRONTEND_PORT` if those defaults are occupied.
Playwright refuses to reuse listeners on the selected ports so an old Next.js
build cannot satisfy the smoke test.

## CI

The GitHub Actions frontend job uses Node.js 24 and runs:

```bash
npm ci
npm run security:audit
npm run lint
npm run typecheck
npm run test:auth-runtime
npm run build
```

The browser job installs the constrained backend runtime, a checksum-verified
Tectonic binary, and Playwright Chromium. It then runs `npm run test:e2e` and
uploads the HTML report, traces, screenshots, and failure evidence for 14 days.

## OpenClaw WebChat / dashboard path

The dashboard supports this OpenClaw flow only in private local auth mode:

```bash
openclaw models set google-vertex/<model-id>
openclaw gateway run --bind loopback
openclaw dashboard
```

Keep Google Cloud credentials and OpenClaw gateway tokens in local environment or OpenClaw config, not in Git.
