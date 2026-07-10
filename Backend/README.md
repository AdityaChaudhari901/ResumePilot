# ResumePilot

ResumePilot is an evidence-backed job application copilot built from the original Job Application Copilot MVP docs. Deterministic resume parsing, job parsing, matching, and claim validation remain the source of truth. Eligible users can request live drafting through a LangGraph workflow that runs LangChain model calls inside graph nodes and pauses for approval before applying generated text.

## Current MVP Slice

- FastAPI backend.
- SQLite persistence for local development and PostgreSQL for production.
- Strict Pydantic contracts.
- Resume upload for PDF, DOCX, TXT, and Markdown.
- Pasted job description analysis and public URL fetch support.
- Durable idempotent analysis and PDF operations with leased worker claims,
  heartbeats, retries, cancellation, progress, and dead-letter visibility.
- Optional Playwright Chromium fallback for JavaScript-rendered public job pages.
- Deterministic skill matching and report generation.
- LangGraph live-draft workflow with PostgreSQL checkpoints and deterministic fallback.
- LangChain structured-output calls inside bounded fit, cover-letter, and interview nodes.
- Durable `waiting_for_approval` operations that resume after an idempotent tenant-owned decision.
- Persisted workflow traces with step latency, provider/model, token usage, approval outcome, and configured provider cost estimates.
- Evidence-backed ATS, cover letter, and interview-prep sections.
- Validation gate for bullets, matched skills, cover letters, supported keywords, and interview evidence IDs.
- Tenant-scoped tailored resume draft workspace for accepting/rejecting generated bullets before final export.
- Deterministic backend quality gate for schema validity, evidence gaps, unsupported claims, required-skill routing, sensitive-output checks, and latency.
- Accepted-draft-only LaTeX and DOCX resume exports using validated uploaded facts.
- Guarded asynchronous PDF resume export compiled by the worker from the same
  accepted evidence-backed draft.
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
`requirements/py312-dev.constraints.txt` so the local and production-compatible
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
python scripts/migrate_runtime.py
```

The repository includes a root `docker-compose.yml` with PostgreSQL, one-shot
migrations, separate FastAPI API and worker roles, and Next.js. See
`../Docs/DEPLOYMENT.md`.

## Optional Live LangGraph Mode

The default bootstrap installs the backend and `dev` extra. To run the install
manually, use Python 3.12 with the pinned constraints:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]" -c requirements/py312-dev.constraints.txt
```

Then set:

```env
AGENT_WORKFLOW_MODE=langgraph
LLM_PROVIDER=vertex
VERTEX_PROJECT_ID=your-google-cloud-project
VERTEX_REGION=global
LLM_MODEL=gemini-3.5-flash
LLM_TIMEOUT_SECONDS=60
LLM_TEMPERATURE=0.2
LLM_MAX_RETRIES=2
LANGGRAPH_STRICT_MSGPACK=true
LANGSMITH_TRACING=false
WORKFLOW_CHECKPOINT_RECONCILE_SECONDS=60
```

Live drafting also requires a premium-plan user and per-analysis consent. The worker creates a validated proposal, changes the operation to `waiting_for_approval`, and releases its lease. `POST /operations/{operation_id}/approval` resumes the same checkpoint. Approval applies the proposal; rejection keeps the deterministic report. Provider or graph failures return the deterministic report with a `langgraph_unavailable` warning.

Provider calls are at-least-once across the narrow crash window between a Vertex
response and the node checkpoint commit. Completed checkpointed nodes are not
replayed. Normal terminal paths delete checkpoints directly; the worker also
removes orphan and terminal threads at startup and on the configured reconciliation
interval.

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
python -m pip install -e ".[dev]" -c requirements/py312-dev.constraints.txt
ruff format app tests scripts migrations --check
ruff check .
pytest
python -m compileall app tests scripts
python scripts/run_golden_evals.py
python scripts/run_backend_quality_gate.py
```

The job uploads `evals/outputs/backend_quality_gate.json` as a short-retention
artifact. Live LangGraph/Vertex checks remain local/manual because they require
provider credentials and networked model calls.

The production image installs the hash-locked LangGraph/LangChain runtime from
`requirements/py312-production.lock.txt`. The one-shot migration service runs
Alembic and `PostgresSaver.setup()` before the API and worker start. Attach a
least-privilege Google service account or Workload Identity for live Vertex
calls; do not bake credential JSON into the image.

## API Surface

- `GET /health`
- `GET /ready`
- `GET /applications`
- `POST /applications`
- `GET /applications/{application_id}`
- `PATCH /applications/{application_id}/status`
- `GET /applications/{application_id}/tailored-resume`
- `PATCH /applications/{application_id}/tailored-resume/items/{item_id}`
- `POST /applications/{application_id}/tailored-resume/latex`
- `POST /applications/{application_id}/tailored-resume/docx`
- `POST /applications/{application_id}/tailored-resume/pdf`
- `POST /resumes/upload`
- `DELETE /resumes/{resume_id}`
- `POST /jobs/preview`
- `POST /jobs/analyze`
- `GET /operations`
- `GET /operations/{operation_id}`
- `POST /operations/{operation_id}/cancel`
- `POST /operations/{operation_id}/approval`
- `GET /operations/{operation_id}/artifact`
- `GET /reports/{report_id}`
- `POST /reports/{report_id}/markdown`
- `GET /reports/{report_id}/trace`
- `DELETE /reports/{report_id}`
- `GET /audit/events`
- `POST /retention/purge`
- `DELETE /account` with `X-Confirm-Account-Deletion: delete-my-account`
- `POST /chat/openclaw`

`POST /jobs/preview` fetches a public job listing URL, extracts structured job
evidence, and returns parser/quality metadata without creating a job or report.
`POST /jobs/analyze` requires an `Idempotency-Key`, accepts either job text/URL
inputs or a persisted `application_id`, and returns `202 Accepted` with an
operation resource. In production, a separate worker fetches/parses, matches,
runs bounded optional AI, validates, and persists the report. Poll the operation
or cancel it through `/operations`; replaying the same key and request returns
the same operation without consuming quota twice.

`POST /applications` saves reviewed job evidence as a tenant-scoped application
draft. `POST /jobs/analyze` can receive `application_id` to complete that draft
with resume/job/report IDs and match score. `PATCH /applications/{id}/status`
supports the dashboard pipeline statuses `draft`, `reviewed`, `analyzed`,
`exported`, and `applied`.

New analyses snapshot `scoring_version=evidence_v2` when queued. The report API
returns an exact component breakdown for required skills, responsibility
evidence, preferred skills, explicit tenure evidence, domain alignment, and the
project/work evidence-strength diagnostic. Not-applicable dimensions are removed
and reweighted; unknown required evidence keeps its effective weight but contributes
zero, so missing information cannot raise the score and makes it provisional. The
UI labels the result as an evidence-fit heuristic rather than a hiring probability.
Historical scores are returned unchanged as `legacy_unversioned` or
`deterministic_v1`. Score metadata lives in additive relational columns so the
stored legacy report/match JSON remains readable by a rollback binary.

`GET /applications/{id}/tailored-resume` creates or returns the application-linked
tailored resume review draft. Users can edit, accept, reject, or reset each
evidence-backed bullet through the item patch route. Application-specific DOCX,
LaTeX, and PDF exports use `POST` because each export reserves usage, records an
audit event, and advances application status atomically. PDF returns a durable
operation and requires an `Idempotency-Key`; its artifact is downloaded from the
authenticated operation route. All resume-document exports include accepted
bullets only and reject unsupported accepted edits before rendering. Generic
report resume-document routes do not exist; Markdown remains report-only.

The `/chat/openclaw` endpoint requires:

```http
Authorization: Bearer <JOBCOPILOT_API_TOKEN>
```

`GET /reports/{report_id}/trace` returns the workflow mode, step statuses,
step summaries, validation warning codes, and optional `duration_ms` timings for
the full workflow and each step. Live LangGraph traces also include the human
approval outcome, provider/model metadata, LangChain message token usage, `cost_estimate_usd`
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
- `app/services` contains deterministic parsing and matching, LangGraph orchestration, LangChain model nodes, report generation, and validation.
- `app/schemas/agent.py` defines structured agent workflow output contracts.
- `app/repositories` owns persistence operations.
- `app/data/skill_dictionary.json` owns the deterministic skill dictionary.
- `migrations` owns database schema migrations.
- `evals` contains synthetic resumes and job descriptions for deterministic regression checks.
