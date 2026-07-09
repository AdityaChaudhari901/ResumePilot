# ResumePilot

ResumePilot is an evidence-backed job application copilot built from the CrewAI Job Application Copilot MVP docs. The backend keeps deterministic resume parsing, job parsing, skill matching, and validation as the source of truth. The agent workflow supports the default deterministic fallback plus an optional live CrewAI mode for bounded, schema-driven explanation and drafting.

## Current MVP Slice

- FastAPI backend.
- SQLite persistence.
- Strict Pydantic contracts.
- Resume upload for PDF, DOCX, TXT, and Markdown.
- Pasted job description analysis and public URL fetch support.
- Optional Playwright Chromium fallback for JavaScript-rendered public job pages.
- Deterministic skill matching and report generation.
- CrewAI-ready agent workflow boundary with deterministic fallback.
- Optional live CrewAI structured-output agents for fit explanation, cover letter drafting, and interview coaching.
- Persisted workflow trace metadata for deterministic fallback versus live CrewAI execution, including latency, provider/model, token usage when exposed by CrewAI, and cost estimates when configured provider pricing matches the trace.
- Evidence-backed ATS, cover letter, and interview-prep sections.
- Validation gate for bullets, matched skills, cover letters, supported keywords, and interview evidence IDs.
- Deterministic backend quality gate for schema validity, evidence gaps, unsupported claims, required-skill routing, sensitive-output checks, and latency.
- Evidence-backed LaTeX resume export using the uploaded resume facts and supported tailored bullets.
- Editable DOCX resume export generated from the same validated report, resume, and job data.
- Guarded PDF resume export compiled from the same evidence-backed LaTeX source.
- Sanitized audit event history for uploads, analyses, exports, deletes, and retention purges.
- Delete and retention purge controls for local resume/report data.
- API token protection for the OpenClaw endpoint.

## Local Setup

```bash
scripts/bootstrap_py312.sh --recreate
source .venv/bin/activate
cp .env.example .env
uvicorn app.main:app --reload
```

Open Swagger UI at `http://127.0.0.1:8000/docs`.

`GET /health` is a liveness check. `GET /ready` checks database connectivity and
optionally verifies that the database revision matches Alembic head.

The backend runtime is pinned to Python `>=3.12,<3.14`. The bootstrap script uses
`requirements/py312-dev-ai.constraints.txt` so the local dev and live CrewAI
dependency graph stays reproducible.

PDF export requires a local LaTeX compiler. `tectonic` is preferred because the
backend can run it with `--untrusted`; `pdflatex` is supported as a fallback with
`-no-shell-escape`. The default compiler timeout is 20 seconds and the default
PDF size limit is 5 MB:

```env
LATEX_COMPILE_TIMEOUT_SECONDS=20
LATEX_PDF_MAX_BYTES=5242880
```

JavaScript-rendered public job pages can use the optional Python Playwright
fallback after a normal `requests` fetch returns too little readable text. The
fallback is not used for blocked/private/rate-limited pages. Install Chromium
locally when you need this path:

```bash
python -m playwright install chromium
```

```env
ENABLE_JOB_BROWSER_FALLBACK=true
JOB_BROWSER_TIMEOUT_MS=8000
```

Retention is disabled by default. Set a positive day count and call the purge
endpoint to remove expired resumes, reports, orphan jobs, and uploaded files:

```env
DATA_RETENTION_DAYS=30
```

## Production Runtime Contract

Production runs must use PostgreSQL and Alembic migrations:

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://user:password@host:5432/resumepilot
AUTH_REQUIRED=true
AUTH_TRUSTED_PROXY_SECRET=<long-random-shared-secret>
JOBCOPILOT_API_TOKEN=<long-random-token>
AUTO_CREATE_DB_SCHEMA=false
REQUIRE_DB_MIGRATIONS=true
```

When `APP_ENV=production`, the backend refuses to start with SQLite, missing
signed-proxy auth, missing OpenClaw token, schema auto-creation, enabled debug
mode, or disabled migration readiness checks. Production schema changes must go
through Alembic:

```bash
alembic upgrade head
```

The repository includes a root `docker-compose.yml` with PostgreSQL, migrated
FastAPI, and Next.js services. See `../Docs/DEPLOYMENT.md`.

## Optional Live CrewAI Mode

The default bootstrap installs the `dev` and `ai` extras. To run the install
manually, use Python 3.12 with the pinned constraints:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,ai]" -c requirements/py312-dev-ai.constraints.txt
```

The `ai` extra installs CrewAI with the native Google Gen AI provider used by the
`google/` model prefix.

Then set:

```env
AGENT_WORKFLOW_MODE=crewai
LLM_PROVIDER=vertex
VERTEX_PROJECT_ID=alien-slice-499511-f8
VERTEX_REGION=global
LLM_MODEL=gemini-3.5-flash
CREWAI_LLM_MODEL=google/gemini-3.5-flash
```

If CrewAI or the provider runtime is unavailable, the API returns the deterministic fallback report and adds a `crewai_unavailable` validation warning instead of failing the analysis request.

## Useful Commands

```bash
pytest
ruff format app tests scripts migrations --check
ruff check .
python -m compileall app tests
python scripts/run_golden_evals.py
python scripts/run_backend_quality_gate.py
alembic upgrade head
```

`scripts/run_backend_quality_gate.py` writes an ignored JSON report to
`evals/outputs/backend_quality_gate.json`. The latest local run measured 20
golden resume/JD pairs with 100% schema pass rate, 0 evidence gaps, 0
unsupported warnings, 0 required-skill routing gaps, 0 sensitive-output hits,
2.06 ms average latency, and 2.47 ms p95 latency in deterministic fallback mode.

## CI

The GitHub Actions backend job runs on Python 3.12 using the pinned constraints
file with the `dev` extra only. It intentionally stays deterministic and
secret-free:

```bash
python -m pip install -e ".[dev]" -c requirements/py312-dev-ai.constraints.txt
ruff format app tests scripts migrations --check
ruff check .
pytest
python -m compileall app tests scripts
python scripts/run_golden_evals.py
python scripts/run_backend_quality_gate.py
```

The job uploads `evals/outputs/backend_quality_gate.json` as a short-retention
artifact. Live CrewAI/Vertex checks remain local/manual because they require
provider credentials and networked model calls.

## API Surface

- `GET /health`
- `GET /ready`
- `GET /applications`
- `POST /applications`
- `PATCH /applications/{application_id}/status`
- `POST /resumes/upload`
- `DELETE /resumes/{resume_id}`
- `POST /jobs/preview`
- `POST /jobs/analyze`
- `GET /reports/{report_id}`
- `GET /reports/{report_id}/markdown`
- `GET /reports/{report_id}/trace`
- `GET /reports/{report_id}/resume/latex`
- `GET /reports/{report_id}/resume/docx`
- `GET /reports/{report_id}/resume/pdf`
- `DELETE /reports/{report_id}`
- `GET /audit/events`
- `POST /retention/purge`
- `POST /chat/openclaw`

`POST /jobs/preview` fetches a public job listing URL, extracts structured job
evidence, and returns parser/quality metadata without creating a job or report.
`POST /jobs/analyze` accepts either the legacy job text/URL inputs or a
`reviewed_job_profile`; dashboard analysis uses the reviewed profile so user
corrections are the source of truth.

`POST /applications` saves reviewed job evidence as a tenant-scoped application
draft. `POST /jobs/analyze` can receive `application_id` to complete that draft
with resume/job/report IDs and match score. `PATCH /applications/{id}/status`
supports the dashboard pipeline statuses `draft`, `reviewed`, `analyzed`,
`exported`, and `applied`.

The `/chat/openclaw` endpoint requires:

```http
Authorization: Bearer <JOBCOPILOT_API_TOKEN>
```

`GET /reports/{report_id}/trace` returns the workflow mode, step statuses,
step summaries, validation warning codes, and optional `duration_ms` timings for
the full workflow and each step. Live CrewAI traces also include provider/model
metadata, optional token usage from CrewAI's LLM summary, `cost_estimate_usd`
when a matching rate exists in `app/data/provider_pricing.json`, and runtime
metadata describing the pricing source. Older persisted traces without these
optional fields remain valid.

The current pricing table is intentionally scoped to the configured
Vertex/global standard path for `google/gemini-3.5-flash`. Cost estimates are
computed from captured prompt, cached prompt, and completion tokens only; if
token split data or a provider/model/region rate is missing, the trace stores
`cost_estimate_usd: null`.

## Accuracy Rule

The deterministic matcher and validator are the source of truth. Generated output must cite resume evidence IDs. Unsupported claims are blocked or marked as "add only if true"; the system must not invent work history, tools, employers, metrics, certifications, or degrees.

## Project Boundaries

- `app/api` contains HTTP routes and dependencies only.
- `app/services` contains deterministic parsing, matching, optional CrewAI execution, report generation, and validation.
- `app/schemas/agent.py` defines structured agent workflow output contracts.
- `app/repositories` owns persistence operations.
- `app/data/skill_dictionary.json` owns the deterministic skill dictionary.
- `migrations` owns database schema migrations.
- `evals` contains synthetic resumes and job descriptions for deterministic regression checks.
