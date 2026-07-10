# ResumePilot Frontend

Next.js dashboard for the local ResumePilot MVP.

## Stack

- Next.js App Router
- React and TypeScript
- Tailwind CSS
- Server route handlers as a backend-for-frontend proxy to FastAPI
- Playwright browser smoke tests

## Current dashboard capabilities

- Guided workflow: job URL or pasted description, reviewed job evidence, resume
  upload, durable AI analysis, validated report, and tailored resume approval.
- Application pipeline workspace backed by `/api/applications`, with saved reviewed drafts and `reviewed`, `analyzed`, `exported`, and `applied` statuses.
- Job preview through `/api/jobs/preview` so users can inspect and edit extracted role, company, skills, responsibilities, and extraction quality before upload.
- Resume upload through the same-origin `/api/resumes/upload` proxy after the job evidence is reviewed.
- Job analysis through `/api/jobs/analyze` using the saved reviewed source
  snapshot, with operation progress, cancellation, safe failures, and retry-safe
  idempotency.
- Per-analysis live AI consent for eligible plans; deterministic processing remains the default and provider prompts exclude candidate contact details.
- Tailored resume workspace through `/api/applications/[applicationId]/tailored-resume` where users edit, accept, or reject evidence-backed bullets before final DOCX, LaTeX, or PDF export.
- Report viewing with JSON, Markdown, workflow trace timings/runtime metadata,
  provider token/cost estimates, claim-validation status, cover-letter and
  interview-prep panels, and evidence comparisons. Resume DOCX/LaTeX/PDF
  downloads are available only from the accepted application draft.
- Collapsed workspace review for report history, parsed resume evidence, account/session state, usage limits, OpenClaw Gateway/provider readiness, and validation boundaries.

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
progress/cancellation behavior, workflow trace timing, Markdown report export,
accepted-draft DOCX/LaTeX/PDF exports, application status transitions, security headers, and
the automated WCAG A/AA baseline. It captures
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
