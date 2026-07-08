# ResumePilot Frontend

Next.js dashboard for the local ResumePilot MVP.

## Stack

- Next.js App Router
- React and TypeScript
- Tailwind CSS
- Server route handlers as a backend-for-frontend proxy to FastAPI
- Playwright browser smoke tests

## Current dashboard capabilities

- Resume upload through the same-origin `/api/resumes/upload` proxy.
- Job analysis through `/api/jobs/analyze`.
- Report viewing with JSON, Markdown, workflow trace timings/runtime metadata, provider token/cost estimates, LaTeX `.tex`, and PDF downloads.
- OpenClaw Gateway/provider readiness status.

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

The smoke command builds the frontend, starts FastAPI on `127.0.0.1:8040`,
starts the production Next.js server on `127.0.0.1:3040`, uploads the backend
sample resume, analyzes the sample job, verifies workflow trace timing and
Markdown/LaTeX/PDF exports, and captures desktop/mobile screenshots under
`Frontend/.local/playwright-results`.

Override ports with `RESUMEPILOT_E2E_BACKEND_PORT` and
`RESUMEPILOT_E2E_FRONTEND_PORT` if those defaults are occupied.

## CI

The GitHub Actions frontend job uses Node.js 24 and runs the static checks that
do not require browser services:

```bash
npm ci
npm run lint
npm run typecheck
```

Playwright remains a local/manual smoke gate for now because it starts FastAPI,
builds the production Next.js server, verifies export endpoints, and captures
screenshots.

## OpenClaw WebChat / dashboard path

The dashboard is aligned with the OpenClaw local Gateway flow:

```bash
openclaw models set google-vertex/<model-id>
openclaw gateway run --bind loopback
openclaw dashboard
```

Keep Google Cloud credentials and OpenClaw gateway tokens in local environment or OpenClaw config, not in Git.
