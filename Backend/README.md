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
- Persisted workflow trace metadata for deterministic fallback versus live CrewAI execution.
- Evidence-backed ATS, cover letter, and interview-prep sections.
- Validation gate for bullets, matched skills, cover letters, supported keywords, and interview evidence IDs.
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
alembic upgrade head
```

## API Surface

- `GET /health`
- `POST /resumes/upload`
- `POST /jobs/analyze`
- `GET /reports/{report_id}`
- `GET /reports/{report_id}/markdown`
- `GET /reports/{report_id}/trace`
- `POST /chat/openclaw`

The `/chat/openclaw` endpoint requires:

```http
Authorization: Bearer <JOBCOPILOT_API_TOKEN>
```

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
