# ResumePilot

ResumePilot is an evidence-backed job application copilot built from the CrewAI Job Application Copilot MVP docs. The backend keeps deterministic resume parsing, job parsing, skill matching, and validation as the source of truth. The agent workflow supports the default deterministic fallback plus an optional live CrewAI mode for bounded, schema-driven explanation and drafting.

## Current MVP Slice

- FastAPI backend.
- SQLite persistence.
- Strict Pydantic contracts.
- Resume upload for PDF, DOCX, TXT, and Markdown.
- Pasted job description analysis and public URL fetch support.
- Deterministic skill matching and report generation.
- CrewAI-ready agent workflow boundary with deterministic fallback.
- Optional live CrewAI structured-output agents for fit explanation, cover letter drafting, and interview coaching.
- Persisted workflow trace metadata for deterministic fallback versus live CrewAI execution, including latency, provider/model, token usage when exposed by CrewAI, and cost placeholders.
- Evidence-backed ATS, cover letter, and interview-prep sections.
- Validation gate for bullets, matched skills, cover letters, supported keywords, and interview evidence IDs.
- Deterministic backend quality gate for schema validity, evidence gaps, unsupported claims, required-skill routing, sensitive-output checks, and latency.
- Evidence-backed LaTeX resume export using the uploaded resume facts and supported tailored bullets.
- Guarded PDF resume export compiled from the same evidence-backed LaTeX source.
- API token protection for the OpenClaw endpoint.

## Local Setup

```bash
scripts/bootstrap_py312.sh --recreate
source .venv/bin/activate
cp .env.example .env
uvicorn app.main:app --reload
```

Open Swagger UI at `http://127.0.0.1:8000/docs`.

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

## API Surface

- `GET /health`
- `POST /resumes/upload`
- `POST /jobs/analyze`
- `GET /reports/{report_id}`
- `GET /reports/{report_id}/markdown`
- `GET /reports/{report_id}/trace`
- `GET /reports/{report_id}/resume/latex`
- `GET /reports/{report_id}/resume/pdf`
- `POST /chat/openclaw`

The `/chat/openclaw` endpoint requires:

```http
Authorization: Bearer <JOBCOPILOT_API_TOKEN>
```

`GET /reports/{report_id}/trace` returns the workflow mode, step statuses,
step summaries, validation warning codes, and optional `duration_ms` timings for
the full workflow and each step. Live CrewAI traces also include provider/model
metadata, optional token usage from CrewAI's LLM summary, `cost_estimate_usd`
when available, and runtime metadata describing whether token/cost data was
reported. Older persisted traces without these optional fields remain valid.

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
