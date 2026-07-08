# ResumePilot Context

Last updated: 2026-07-08

## Purpose

ResumePilot is being created from the CrewAI Job Application Copilot MVP documentation pack. The application will be a local-first, evidence-backed job application copilot that compares a user's resume with a job description and returns a truthful job-fit report, tailored resume suggestions, ATS keywords, a cover letter draft, and interview preparation.

## Current Workspace State

- Root path: `/Users/adityachaudhari/Desktop/ResumePilot`
- Current state: four-folder workspace created; backend foundation, Python 3.12 locked backend runtime, deterministic backend speed/accuracy quality gate, evidence-backed LaTeX and PDF resume export, live CrewAI structured-output workflow adapter verified against Google Vertex with deterministic fallback, persisted workflow trace metadata with latency/provider/model/token usage/cost observability, project-local OpenClaw `/job` skill, Next.js WebChat/dashboard workbench with Markdown, LaTeX, and PDF report downloads, and Playwright dashboard browser smoke implemented.
- Git state: initialized on branch `main`.
- Git remote: `origin` -> `https://github.com/AdityaChaudhari901/ResumePilot.git`.
- Workspace folders:
  - `Frontend/`
  - `Backend/`
  - `Ai services/`
  - `Docs/`
- Existing source material:
  - `Docs/CrewAI_Job_Application_Copilot_MVP_Docs.md`
  - `Docs/crewai-job-copilot-mvp-docs/README.md`
  - `Docs/crewai-job-copilot-mvp-docs/docs/*.md`
  - `Docs/crewai-job-copilot-mvp-docs/schemas/application_report.schema.json`
  - `Docs/crewai-job-copilot-mvp-docs/schemas/resume_profile.schema.json`
- Implemented application structure:
  - `Backend/app/main.py`
  - `Backend/app/api/routes/*.py`
  - `Backend/app/core/*.py`
  - `Backend/app/db/*.py`
  - `Backend/app/repositories/*.py`
  - `Backend/app/schemas/*.py`
  - `Backend/app/schemas/agent.py`
  - `Backend/app/services/*.py`
  - `Backend/app/services/agent_workflow.py`
  - `Backend/app/services/crewai_workflow.py`
  - `Backend/app/services/provider_pricing.py`
  - `Backend/app/services/latex_resume_renderer.py`
  - `Backend/app/services/pdf_resume_compiler.py`
  - `Backend/app/data/provider_pricing.json`
  - `Backend/app/data/skill_dictionary.json`
  - `Backend/migrations/*.py`
  - `Backend/tests/*.py`
  - `Backend/tests/test_agent_workflow.py`
  - `Backend/tests/test_backend_quality_gate.py`
  - `Backend/tests/test_latex_resume_renderer.py`
  - `Backend/tests/test_pdf_resume_compiler.py`
  - `Backend/scripts/run_golden_evals.py`
  - `Backend/scripts/run_backend_quality_gate.py`
  - `Backend/scripts/bootstrap_py312.sh`
  - `Backend/requirements/py312-dev-ai.constraints.txt`
  - `Backend/evals/resumes/*.md`
  - `Backend/evals/jobs/*.txt`
  - `Frontend/e2e/*.ts`
  - `Frontend/playwright.config.ts`
  - `Ai services/openclaw/workspace/skills/job/SKILL.md`
  - `Ai services/openclaw/workspace/skills/job/scripts/resumepilot_job.py`
  - `Ai services/openclaw/tests/test_resumepilot_job.py`
- Verified: both JSON schema files are valid JSON.
- System Python observed: Python 3.14.3.
- Backend runtime standard: Python 3.12.13 via `.python-version` and `Backend/scripts/bootstrap_py312.sh`.
- `uv` is not currently available in the outer shell PATH; the backend Python 3.12 environment installs pinned `uv==0.11.28` as a CrewAI CLI dependency.
- Local virtual environment at `Backend/.venv` recreated with Python 3.12.13 and pinned backend dev+AI constraints.
- Local TeX compiler observed: `tectonic 0.16.9`.
- Python 3.12 live CrewAI verification environment created under ignored path `Backend/.local/venvs/py312`.
- Project dependencies are declared in `Backend/pyproject.toml`.
- Backend dependency constraints are pinned in `Backend/requirements/py312-dev-ai.constraints.txt` and used as pip constraints with editable installs.
- Local API server verified on `http://127.0.0.1:8002`.
- Local runtime data for the dev server is stored under `Backend/.local/data`.
- OpenClaw installed locally as `OpenClaw 2026.6.11` using Node.js `v24.16.0`.
- OpenClaw local config exists at `~/.openclaw/openclaw.json`; the included Google plugin is enabled.
- Google Vertex selected as the current OpenClaw provider path (`google-vertex`) with default model `google-vertex/gemini-3.5-flash`.
- Canonical local LLM env names are `LLM_PROVIDER=vertex`, `VERTEX_PROJECT_ID=alien-slice-499511-f8`, `VERTEX_REGION=global`, and `LLM_MODEL=gemini-3.5-flash`.
- Backend workflow mode is controlled by `AGENT_WORKFLOW_MODE`, defaulting to `deterministic_fallback`; `crewai` enables live CrewAI structured-output sections when the runtime is available.
- Live CrewAI mode uses `CREWAI_LLM_MODEL`, `CREWAI_MAX_ITER`, `CREWAI_TIMEOUT_SECONDS`, and `CREWAI_TEMPERATURE`.
- Local Google Cloud ADC is present and the local gcloud project is set from the ADC quota project.
- OpenClaw Gateway service is not installed as a daemon; foreground local startup is handled by `Ai services/openclaw/scripts/start_local_gateway.sh`.
- Frontend app implemented in `Frontend/` with Next.js `16.2.10`, React `19.2.7`, TypeScript, Tailwind CSS, and lucide-react.
- Frontend route handlers proxy browser requests to FastAPI through `RESUMEPILOT_API_BASE_URL`, expose report trace metadata through `/api/reports/[reportId]/trace`, expose LaTeX report download through `/api/reports/[reportId]/resume/latex`, expose PDF report download through `/api/reports/[reportId]/resume/pdf`, and probe OpenClaw Gateway readiness through `/api/openclaw/status`.

## Product Rule

The product must be evidence-first. Deterministic parsing, normalization, matching, scoring, and validation are the source of truth. CrewAI agents may explain, rewrite, draft, and organize output, but they must not invent work history, skills, metrics, employers, certifications, degrees, or achievements.

Every generated resume bullet or matched skill must trace back to resume evidence. Unsupported additions must be rejected or clearly marked as "add only if true".

## Source Of Truth Rule

Before implementing product behavior, architecture changes, AI workflows, backend APIs, frontend UI, tests, or documentation, refer to these project docs so the implementation stays aligned with the ResumePilot use case:

- `Docs/CrewAI_Job_Application_Copilot_MVP_Docs.md`
- `Docs/crewai-job-copilot-mvp-docs/README.md`
- `Docs/crewai-job-copilot-mvp-docs/docs/`

Before implementing or changing live CrewAI behavior, also verify the current official CrewAI documentation:

- `https://docs.crewai.com/`

## Selected MVP Tech Stack

| Layer | Choice |
|---|---|
| Backend API | FastAPI |
| Language | Python 3.12 target runtime |
| Validation | Pydantic v2 |
| Database | SQLite for MVP |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Resume parsing | pypdf, python-docx, TXT, Markdown |
| Job parsing | requests, BeautifulSoup, readability-lxml |
| Browser fallback | Playwright, only when needed |
| Agent orchestration | CrewAI |
| LLM provider layer | CrewAI config or LiteLLM-compatible wrapper |
| Reports | JSON, Markdown, LaTeX `.tex`, and compiled PDF resume export |
| Auth | Local API token via `JOBCOPILOT_API_TOKEN` |
| Frontend | Next.js App Router, React, TypeScript, Tailwind CSS |
| Frontend API bridge | Next.js route handlers as backend-for-frontend proxy |
| OpenClaw model provider path | Google Vertex via `google-vertex` and gcloud ADC |
| Frontend icons | lucide-react |
| Testing | pytest, httpx, respx, Playwright |
| Packaging | Docker Compose later, not required on day one |

## Build Order

1. FastAPI backend foundation.
2. SQLite and SQLAlchemy models.
3. Strict Pydantic schemas for resume, job, match result, report, and validation failures.
4. Resume upload and parser.
5. Job text parser and URL ingestion.
6. Skill normalization and deterministic matcher.
7. Deterministic report generator.
8. Unsupported-claim validation gate.
9. CrewAI agent workflow.
10. OpenClaw `/job` integration.
11. Reliability, caching, background jobs, and optional web UI.

## Near-Term Implementation Scope

Completed first deterministic backend slice before CrewAI:

- Created Python project structure.
- Added FastAPI app and `/health`.
- Added settings and local environment loading.
- Added SQLite models.
- Converted/expanded contracts into strict Pydantic models.
- Added resume upload with PDF, DOCX, TXT, and Markdown support.
- Added pasted job description analysis and basic public URL fetch support.
- Added deterministic skill matcher and report generator.
- Added validation for evidence references and unsupported skill claims.
- Added tests for health, upload, parsing, matching, report retrieval, and OpenClaw auth.

Completed backend hardening after folder restructure:

- Moved implementation into `Backend/`.
- Moved MVP docs into `Docs/`.
- Created `Frontend/` and `Ai services/` placeholders.
- Added Alembic migration setup and initial schema migration.
- Added repository layer for resumes, jobs, and analyses.
- Moved deterministic skill dictionary into `Backend/app/data/skill_dictionary.json`.
- Added richer synthetic eval resumes and job descriptions.
- Added `Backend/scripts/run_golden_evals.py`.
- Added tests for URL fetch fallback, validator behavior, report schema validation, and golden eval execution.

Completed CrewAI-ready deterministic agent workflow boundary:

- Added strict Pydantic contracts for agent workflow steps and outputs.
- Added `Backend/app/services/agent_workflow.py` to mirror the planned JD parser, resume match, ATS optimizer, cover letter, interview coach, and validation gate sequence.
- Kept the current workflow in deterministic fallback mode so the app does not require live LLM keys.
- Routed `/jobs/analyze` and `/chat/openclaw` report generation through the workflow boundary.
- Strengthened validation for cover letter unsupported skills and interview answer evidence IDs.
- Fixed `OPENCLAW_SENDER_ALLOWLIST` parsing so local `.env` can use a simple comma-separated string.
- Added tests for agent workflow trace, report sections, and new validation cases.

Completed OpenClaw local integration:

- Installed OpenClaw CLI locally and verified `openclaw --version`.
- Added a project-local OpenClaw workspace under `Ai services/openclaw/workspace`.
- Added the `job` skill for `/job` and `/skill job` usage.
- Added the `resumepilot_job.py` helper that posts to `POST /chat/openclaw` with bearer-token auth.
- Added helper unit tests and setup documentation for OpenClaw environment variables.
- Verified OpenClaw detects the `job` skill as ready, visible to model, and available as a command.
- Verified helper-to-backend smoke with a sample resume and sample job description.

Completed initial WebChat/dashboard slice:

- Added a production-built Next.js dashboard under `Frontend/`.
- Added server-side route handlers for `/api/health`, resume upload, job analysis, report JSON, report Markdown, and OpenClaw status.
- Kept browser traffic same-origin through the Next.js backend-for-frontend layer instead of exposing backend tokens or adding broad CORS.
- Added resume upload, pasted job analysis, report summary, evidence-backed skill review, Markdown export, and OpenClaw WebChat status panels.
- Documented Google Vertex provider setup and OpenClaw Control UI/WebChat local commands.
- Added an npm override for Next's transitive PostCSS version so frontend production audit reports zero vulnerabilities.
- Verified dashboard proxy flow against FastAPI on `127.0.0.1:8002` and Next.js on `127.0.0.1:3001`.

Completed OpenClaw Gateway and Vertex onboarding slice:

- Added repeatable local scripts for OpenClaw Google Vertex configuration and foreground Gateway startup.
- Added an ignored local Gateway env flow that generates a shared token without committing or printing it.
- Ignored OpenClaw-generated workspace root bootstrap/state files while keeping the project `job` skill tracked.
- Switched the demo Vertex model default to `google-vertex/gemini-3.5-flash` with `VERTEX_REGION=global` after direct Vertex validation confirmed the model works in the selected project.
- Added backend settings support for the canonical Vertex env names so live CrewAI/provider integration can read the same configuration.
- Extended the dashboard OpenClaw status API and card to report live Gateway reachability, provider, model reference, token presence, project readiness, and local commands.
- Verified Vertex ADC and the selected model with a direct Google Vertex REST generation smoke.
- Verified the Gateway starts on loopback, serves the Control UI, and executes the `/job` skill through `openclaw agent` after repairing the local CLI device pairing scope.

Completed optional live CrewAI workflow adapter slice:

- Verified current official CrewAI docs before implementation; live CrewAI requires Python `>=3.10,<3.14` and supports direct agent kickoff with typed Pydantic response formats.
- Added `Backend/app/services/crewai_workflow.py` with bounded CrewAI agents for resume match explanation, cover letter drafting, and interview coaching.
- Kept deterministic parsing, matching, ATS bullets/keywords, and final validation as the source of truth.
- Added safe fallback when CrewAI is missing, provider config is incomplete, or the runtime uses unsupported Python; fallback returns the deterministic report with a `crewai_unavailable` warning.
- Added backend settings and `.env.example` values for `AGENT_WORKFLOW_MODE`, `CREWAI_LLM_MODEL`, `CREWAI_MAX_ITER`, `CREWAI_TIMEOUT_SECONDS`, and `CREWAI_TEMPERATURE`.
- Added an optional `ai` dependency extra for `crewai[google-genai]` on Python `<3.14`.
- Routed `/jobs/analyze` and `/chat/openclaw` through app settings so workflow mode is controlled by the active FastAPI configuration.

Completed live CrewAI + Vertex smoke:

- Corrected the backend `ai` optional dependency to `crewai[google-genai]` after CrewAI `1.15.2` reported the required native provider extra for `google/` models.
- Created a Python 3.12 local verification environment at `Backend/.local/venvs/py312`.
- Installed the backend with `.[dev,ai]`, including CrewAI `1.15.2` and Google Gen AI SDK `1.65.0`.
- Verified CrewAI initializes `LLM(model="google/gemini-3.5-flash")` as `GeminiCompletion`.
- Ran the ResumePilot workflow in `AGENT_WORKFLOW_MODE=crewai`; trace mode returned `crewai` and completed resume match, cover letter, and interview coach agent steps.
- Ran the real FastAPI HTTP path on `127.0.0.1:8012`; upload, analyze, report JSON, and report Markdown all passed, and three Vertex `generateContent` calls returned HTTP 200.

Completed workflow trace persistence and dashboard visibility slice:

- Added `workflow_mode` and `workflow_trace_json` to persisted analyses with an Alembic migration and backward-compatible defaults for existing rows.
- Stored the deterministic fallback, CrewAI success, or CrewAI unavailable fallback trace after every analysis.
- Added `GET /reports/{report_id}/trace` and the matching Next.js `/api/reports/[reportId]/trace` proxy.
- Added a dashboard workflow trace panel that shows live CrewAI versus deterministic fallback mode, step status, summaries, and validation warning codes.
- Added API tests for deterministic trace persistence, CrewAI fallback persistence, and mocked CrewAI success persistence.
- Updated backend/docs API references to include the trace endpoint.

Completed workflow trace timing telemetry slice:

- Added backward-compatible `duration_ms` fields to workflow traces and trace steps.
- Measured deterministic workflow steps, live CrewAI runtime execution, individual CrewAI agent sections, ATS regeneration, validation, and total workflow latency with monotonic timers.
- Persisted trace timing through existing report trace JSON so old traces without timing fields still validate.
- Added dashboard rendering for total workflow duration and per-step durations.
- Added backend and Playwright assertions for timing telemetry shape and visibility.
- Updated backend/frontend README files and MVP docs with the trace timing contract.

Completed live runtime provider observability slice:

- Added backward-compatible trace fields for live provider, model, token usage, cost estimate, and runtime metadata.
- Extracted token usage from CrewAI's LLM summary when the live runtime exposes it.
- Persisted provider/model/token metadata through existing `workflow_trace_json` without a database migration.
- Rendered a compact dashboard runtime section for traces that include provider metadata.
- Added backend/API tests for legacy traces, deterministic traces, CrewAI fallback metadata, and CrewAI success token usage.

Completed provider pricing cost estimate slice:

- Added `Backend/app/data/provider_pricing.json` as a versioned provider pricing table for the configured Vertex global standard `google/gemini-3.5-flash` path.
- Added `Backend/app/services/provider_pricing.py` to compute cost estimates from captured prompt, cached prompt, and completion token usage with Decimal math and strict provider/model/region matching.
- Populated live CrewAI `cost_estimate_usd` and runtime pricing metadata when CrewAI token usage matches the configured pricing source.
- Kept deterministic traces, legacy traces, CrewAI fallback traces, and unconfigured provider/model/region traces cost-null instead of guessing.
- Updated backend/API tests, README files, and MVP docs for pricing-backed workflow trace metadata.

Completed backend Python 3.12 runtime and dependency lock slice:

- Added root `.python-version` with Python `3.12.13`.
- Tightened backend package metadata to Python `>=3.12,<3.14` so unsupported Python 3.14 installs are rejected before CrewAI setup.
- Added `Backend/requirements/py312-dev-ai.constraints.txt` generated from the verified Python 3.12 dev+AI environment.
- Added `Backend/scripts/bootstrap_py312.sh` to create or recreate a Python 3.12 backend virtualenv with the pinned constraints.
- Recreated the default ignored `Backend/.venv` as Python 3.12.13 using the bootstrap script.
- Updated root and backend README setup commands to use the Python 3.12 bootstrap path.

Completed deterministic backend speed/accuracy quality gate slice:

- Added `Backend/scripts/run_backend_quality_gate.py` for a repeatable backend readiness gate before frontend expansion.
- The gate runs the existing 4 resume x 5 job golden corpus through deterministic parsing, matching, workflow report generation, Pydantic schema validation, evidence validation, required-skill routing checks, sensitive-output checks, and latency measurement.
- Default thresholds require 100% schema pass rate, 0 evidence gaps, 0 unsupported warning counts, 0 required-skill routing gaps, 0 sensitive-output hits, average latency under 500 ms, and p95 latency under 1500 ms.
- Added focused tests for the gate and threshold failure explanations.
- Updated backend README and testing docs with the quality-gate command and measured local deterministic results.

Completed evidence-backed LaTeX resume export backend slice:

- Added `Backend/app/services/latex_resume_renderer.py` using Aditya's compact one-page ATS LaTeX resume structure.
- Added `GET /reports/{report_id}/resume/latex`, returning a downloadable `.tex` file with `application/x-tex` media type and a stable attachment filename.
- The LaTeX export renders candidate/contact data, professional summary, evidence-backed skills, tailored resume highlights, experience, projects, education, and certifications from persisted `ResumeProfile`, `JobProfile`, and `ApplicationReport` data.
- The renderer escapes LaTeX metacharacters and excludes missing or `add_only_if_true` skills from owned resume sections.
- Added focused tests for LaTeX escaping, missing-skill exclusion, and API download behavior.
- Updated backend README and architecture docs with the new report export endpoint.

Completed dashboard LaTeX download slice:

- Added a Next.js backend-for-frontend proxy route at `Frontend/src/app/api/reports/[reportId]/resume/latex/route.ts`.
- Preserved backend `Content-Disposition` headers through the shared frontend proxy helper.
- Added a `LaTeX` download button beside the existing Markdown export in the report viewer.
- Updated the frontend README to include JSON, Markdown, workflow trace, and LaTeX report download capabilities.
- Verified frontend lint, typecheck, production build, and a live upload/analyze/download smoke through the Next.js LaTeX proxy route.

Completed evidence-backed PDF resume export slice:

- Added `Backend/app/services/pdf_resume_compiler.py` to compile generated LaTeX with a guarded local compiler boundary.
- Preferred `tectonic --untrusted`, added `pdflatex -no-shell-escape` fallback, and enforced no shell invocation, temporary workspaces, timeout limits, and output-size limits.
- Added `GET /reports/{report_id}/resume/pdf`, returning a downloadable `application/pdf` attachment from the same persisted report data as the LaTeX export.
- Added a Next.js backend-for-frontend proxy route at `Frontend/src/app/api/reports/[reportId]/resume/pdf/route.ts`.
- Added a dashboard `PDF` download button beside Markdown and LaTeX exports.
- Updated backend/frontend/root README files and source-of-truth docs with the PDF endpoint, compiler requirements, and report export safety controls.
- Added focused compiler and API tests for successful PDF downloads, missing compiler handling, compiler command safety, and output-size enforcement.
- Verified local `tectonic 0.16.9` compiles both a minimal document and the generated ResumePilot LaTeX template.

Completed dashboard Playwright browser smoke slice:

- Added Playwright to the frontend dev toolchain with `npm run test:e2e:install` and `npm run test:e2e`.
- Added `Frontend/playwright.config.ts` to build the frontend, start FastAPI on `127.0.0.1:8040`, start production Next.js on `127.0.0.1:3040`, and run Chromium tests with ignored local artifacts.
- Added `Frontend/e2e/dashboard.spec.ts` covering resume upload, sample job analysis, report rendering, workflow trace visibility, Markdown/LaTeX/PDF export response checks, and desktop/mobile screenshots.
- Updated root/frontend README files and testing docs with the browser smoke command and artifact locations.
- Verified Playwright Chromium setup and the dashboard e2e smoke with 2 passing browser tests.

Next implementation scope:

- Add report export polish, saved export history or DOCX export, live-provider latency/cost aggregation in the backend quality gate, and CI artifact upload or screenshot baseline comparisons.

## Known Gaps

- Existing original JSON schemas are valid but looser than the implemented Pydantic contracts.
- OpenClaw APIs should be verified against current official docs before live integration.
- Backend lock is a pinned pip constraints file, not a hash-locked artifact; add hash locking or container builds before remote production deployment.
- The new backend quality gate measures deterministic local backend latency only; live CrewAI/provider latency and token usage are visible in per-report traces but not included in the deterministic quality gate yet.
- PDF export is implemented with local `tectonic` verification; remote production deployment should preinstall/cache the TeX toolchain and consider an OS/container sandbox for compilation.
- DOCX export is not implemented yet.
- Workflow trace cost estimates currently cover only the configured Vertex global standard `google/gemini-3.5-flash` path; additional provider/model/region rates must be added before other traces can emit cost.
- Background queue, caching, metrics, and visual screenshot baseline regression are not implemented yet.
- Playwright browser smoke is implemented; CI artifact upload, screenshot baseline diffing, and accessibility audits are not implemented yet.

## Verification Evidence

Latest verification run: 2026-07-08

| Check | Command | Result |
|---|---|---|
| Python runtime | `cd Backend && .venv/bin/python --version && .venv/bin/python -m pip check` | Passed: Python 3.12.13, no broken requirements |
| Backend bootstrap | `VENV_DIR=.local/venvs/bootstrap-check Backend/scripts/bootstrap_py312.sh --recreate` | Passed: fresh Python 3.12.13 constrained install, `pip check` passed |
| Backend default venv bootstrap | `Backend/scripts/bootstrap_py312.sh --recreate` | Passed: recreated `Backend/.venv` as Python 3.12.13 with pinned dev+AI constraints |
| TeX compiler | `tectonic --version` | Passed: `Tectonic 0.16.9` |
| Tests | `cd Backend && .venv/bin/pytest` | Passed: 34 passed, 1 Starlette/httpx deprecation warning |
| Report export focused tests | `cd Backend && .venv/bin/pytest tests/test_pdf_resume_compiler.py tests/test_analysis_api.py tests/test_settings.py` | Passed: 10 passed, 1 Starlette/httpx deprecation warning |
| Backend trace timing coverage | `cd Backend && .venv/bin/pytest` | Passed: workflow trace timing assertions covered in full backend run, 34 passed |
| Backend runtime pricing focused tests | `cd Backend && .venv/bin/pytest tests/test_provider_pricing.py tests/test_agent_workflow.py tests/test_analysis_api.py` | Passed: 14 passed, 1 Starlette/httpx deprecation warning |
| Lint | `cd Backend && .venv/bin/ruff format app tests scripts migrations --check && .venv/bin/ruff check .` | Passed: 68 files already formatted, all checks passed |
| Compile | `cd Backend && .venv/bin/python -m compileall app tests scripts` | Passed |
| Migration | `cd Backend && DATABASE_URL=sqlite:///./.local/data/py312-lock-migration-check.db RESUMEPILOT_DATA_DIR=.local/data .venv/bin/alembic upgrade head` | Passed: upgraded through `20260708_0002` |
| Golden evals | `cd Backend && .venv/bin/python scripts/run_golden_evals.py` | Passed: 20 pairs evaluated |
| Backend quality gate | `cd Backend && .venv/bin/python scripts/run_backend_quality_gate.py` | Passed: 20 pairs, 100% schema pass, 0 evidence gaps, 0 unsupported warnings, 0 required-skill routing gaps, 0 sensitive-output hits, avg 2.94 ms, p95 4.13 ms |
| Minimal PDF compiler smoke | `cd Backend && .venv/bin/python -c '... compile_latex_to_pdf(...) ...'` | Passed: generated 3617-byte PDF with `%PDF-` prefix |
| Generated ResumePilot PDF smoke | `cd Backend && .venv/bin/python - <<'PY' ... render_tailored_resume_latex(...) ... compile_latex_to_pdf(...) ... PY` | Passed: generated 19397-byte PDF with `%PDF-` prefix |
| Live health | `curl -sS http://127.0.0.1:8002/health` | Passed: `{"status":"ok","app":"ResumePilot","environment":"development"}` |
| Live API smoke | Upload sample resume, analyze sample JD, fetch JSON and Markdown reports | Passed: health 200, upload 201, analyze 200, report 200, markdown 200 |
| Live OpenClaw smoke | `POST /chat/openclaw` with `paste:` job text and allowlisted sender | Passed: 200, status `completed`, Markdown report returned |
| OpenClaw CLI | `openclaw --version` | Passed: `OpenClaw 2026.6.11` |
| OpenClaw skill discovery | `OPENCLAW_WORKSPACE_DIR="$PWD/Ai services/openclaw/workspace" JOBCOPILOT_API_TOKEN=test-token openclaw skills list --eligible` | Passed: `job` ready |
| OpenClaw skill check | `OPENCLAW_WORKSPACE_DIR="$PWD/Ai services/openclaw/workspace" JOBCOPILOT_API_TOKEN=test-token openclaw skills check` | Passed: `job` ready, visible, and available as command |
| OpenClaw helper tests | `python3 -m unittest discover "Ai services/openclaw/tests"` | Passed: 4 tests |
| OpenClaw helper smoke | Upload sample resume, run `resumepilot_job.py paste:<sample job>` against API on port 8002 | Passed: helper exit 0, Markdown report returned |
| Frontend audit | `cd Frontend && npm audit --omit=dev` | Passed: 0 vulnerabilities after PostCSS override |
| Frontend lint | `cd Frontend && PATH="$HOME/.nvm/versions/node/v24.16.0/bin:$PATH" npm run lint` | Passed |
| Frontend typecheck | `cd Frontend && PATH="$HOME/.nvm/versions/node/v24.16.0/bin:$PATH" npm run typecheck` | Passed |
| Frontend build | `cd Frontend && PATH="$HOME/.nvm/versions/node/v24.16.0/bin:$PATH" npm run test:e2e` | Passed: Next.js production build generated the dashboard and API routes including `/api/reports/[reportId]/trace`, `/api/reports/[reportId]/resume/latex`, and `/api/reports/[reportId]/resume/pdf` |
| Playwright Chromium install | `cd Frontend && PATH="$HOME/.nvm/versions/node/v24.16.0/bin:$PATH" npm run test:e2e:install` | Passed: Chromium already available for Playwright |
| Dashboard Playwright browser smoke | `cd Frontend && PATH="$HOME/.nvm/versions/node/v24.16.0/bin:$PATH" npm run test:e2e` | Passed: production build, FastAPI on `127.0.0.1:8040`, Next.js on `127.0.0.1:3040`, 2 Chromium tests passed, workflow trace timing and Markdown/LaTeX/PDF exports verified |
| E2E port cleanup | `lsof -nP -iTCP:8040 -sTCP:LISTEN` and `lsof -nP -iTCP:3040 -sTCP:LISTEN` | Passed: no listeners after Playwright completed |
| Diff whitespace | `git diff --check` | Passed |
| Dashboard screenshots | `Frontend/.local/playwright-results/**/dashboard-desktop.png` and `Frontend/.local/playwright-results/**/dashboard-mobile.png` | Passed: desktop and mobile screenshots captured in ignored local artifacts |
| Dashboard LaTeX proxy smoke | Backend on `127.0.0.1:8033`, Next.js on `127.0.0.1:3033`, upload/analyze/fetch LaTeX through `/api/*` | Passed: health 200, upload 201, analyze 200, LaTeX 200, `content-type: application/x-tex`, attachment filename preserved |
| Dashboard PDF proxy smoke | Backend on `127.0.0.1:8034`, Next.js on `127.0.0.1:3034`, upload/analyze/fetch PDF through `/api/*` | Passed: health 200, upload 201, analyze 200, PDF 200, `content-type: application/pdf`, attachment filename preserved, 19397-byte `%PDF-` payload |
| Dashboard trace proxy smoke | Backend on `127.0.0.1:8020`, Next.js on `127.0.0.1:3020`, upload/analyze/fetch trace through `/api/*` | Passed: report `2`, trace mode `deterministic_fallback`, 6 trace steps |
| OpenClaw Vertex model discovery | `openclaw models list --provider google-vertex --plain` | Passed: listed Google Vertex model refs |
| OpenClaw gateway status | `openclaw gateway status` | Verified not running: service not installed, loopback probe refused |
| OpenClaw Vertex config | `LLM_PROVIDER=vertex VERTEX_PROJECT_ID=alien-slice-499511-f8 VERTEX_REGION=global LLM_MODEL=gemini-3.5-flash ./Ai services/openclaw/scripts/configure_vertex_gateway.sh` | Passed: Google plugin enabled, default model set to `google-vertex/gemini-3.5-flash`, config valid |
| OpenClaw Gateway startup | `JOBCOPILOT_API_TOKEN=test-token ./Ai services/openclaw/scripts/start_local_gateway.sh` | Passed: Gateway ready on `127.0.0.1:18789`, Control UI served HTTP 200 |
| Frontend OpenClaw status | `curl -sS http://127.0.0.1:3003/api/openclaw/status` | Passed: provider `google-vertex`, model `google-vertex/gemini-3.5-flash`, gateway reachable true |
| Vertex ADC model smoke | Direct Vertex REST `generateContent` for `global` / `gemini-3.5-flash` | Passed: model returned `ok` without exposing the access token |
| Backend Vertex settings | `cd Backend && .venv/bin/pytest tests/test_settings.py` | Passed through full backend pytest run |
| OpenClaw device pairing repair | `./Ai services/openclaw/scripts/repair_cli_device_pairing.sh --yes` | Passed: local CLI device approved scopes include `operator.write` and `operator.pairing`; pending requests cleared |
| OpenClaw agent CLI smoke | `openclaw agent --message "/job paste:..." --json` | Passed: Gateway RPC accepted the request and returned a ResumePilot job fit report |
| CrewAI workflow focused tests | `cd Backend && .venv/bin/pytest tests/test_agent_workflow.py tests/test_settings.py` | Passed: 4 passed, 1 Starlette/httpx deprecation warning |
| Golden evals after CrewAI adapter | `cd Backend && .venv/bin/python scripts/run_golden_evals.py` | Passed: 20 pairs evaluated |
| Python 3.12 AI install | `cd Backend && .local/venvs/py312/bin/python -m pip install -e ".[dev,ai]"` | Passed: CrewAI `1.15.2` and Google Gen AI SDK `1.65.0` installed |
| Python 3.12 backend tests | `cd Backend && .local/venvs/py312/bin/pytest` | Passed: 17 passed, 1 Starlette/httpx deprecation warning |
| Python 3.12 lint | `cd Backend && .local/venvs/py312/bin/ruff check .` | Passed |
| Python 3.12 compile | `cd Backend && .local/venvs/py312/bin/python -m compileall app tests scripts` | Passed |
| CrewAI Google provider init | `LLM(model="google/gemini-3.5-flash")` under Python 3.12 with Vertex env | Passed: initialized as `GeminiCompletion` |
| Live CrewAI workflow smoke | `AGENT_WORKFLOW_MODE=crewai ... run_application_agent_workflow(...)` | Passed: trace mode `crewai`, live agent steps completed, no `crewai_unavailable` warning |
| Live CrewAI runtime observability smoke | `AGENT_WORKFLOW_MODE=crewai LLM_PROVIDER=vertex VERTEX_PROJECT_ID=alien-slice-499511-f8 VERTEX_REGION=global LLM_MODEL=gemini-3.5-flash CREWAI_LLM_MODEL=google/gemini-3.5-flash .local/venvs/py312/bin/python - <<'PY' ... PY` | Passed: provider `vertex`, model `google/gemini-3.5-flash`, token usage captured with 9997 total tokens and 3 successful requests, cost estimate remained null |
| Live CrewAI API smoke | FastAPI on `127.0.0.1:8012` with upload/analyze/report/markdown HTTP flow | Passed: health 200, upload 201, analyze 200, report 200, markdown 200, no fallback warning, three Vertex `generateContent` calls returned HTTP 200 |

## Change Log

### 2026-07-08

- Scanned and analyzed the CrewAI Job Application Copilot MVP documentation pack.
- Confirmed this workspace is docs-only and not a git repository.
- Confirmed both JSON schema files parse successfully.
- Selected the MVP stack: FastAPI, Python 3.12, Pydantic v2, SQLite, SQLAlchemy, CrewAI, pytest.
- Created this `Context.md` file.
- Implemented the first deterministic backend slice with FastAPI, SQLite/SQLAlchemy models, strict Pydantic schemas, resume parsing, job parsing, skill matching, report generation, validation, and OpenClaw API-token auth.
- Added sample eval resume and job description.
- Added pytest coverage for health, parsing, matching, upload/analyze/report retrieval, and OpenClaw auth.
- Created `.venv` and installed project dependencies with `python -m pip install -e ".[dev]"`.
- Added Alembic to project dependencies for the upcoming migration setup.
- Verified tests, lint, and compile checks pass.
- Started the local FastAPI server on `127.0.0.1:8001` because port 8000 was already occupied by an `ssh` listener.
- Verified live upload/analyze/report retrieval with `evals/resumes/backend_fresher.md` and `evals/jobs/backend_python_junior.txt`.
- Created four top-level folders: `Frontend/`, `Backend/`, `Ai services/`, and `Docs/`.
- Moved backend implementation, tests, evals, and Python project files into `Backend/`.
- Moved the MVP documentation pack into `Docs/`.
- Added Alembic configuration and initial schema migration.
- Added repository classes for resume, job, and analysis persistence.
- Externalized the deterministic skill dictionary to JSON.
- Added frontend, AI services, docs, and root README files describing project boundaries.
- Added richer eval fixtures and golden eval runner.
- Expanded test coverage from 6 to 11 tests.
- Verified tests, lint, compile, migration, golden evals, and live API smoke pass from the new structure.
- Started the local FastAPI server on `127.0.0.1:8002` because ports 8000 and 8001 were occupied by `ssh` listeners.
- Initialized git, renamed the branch to `main`, and configured GitHub remote `origin`.
- Added the source-of-truth rule requiring future work to refer to the MVP documentation pack before implementation.
- Added CrewAI-ready deterministic agent workflow contracts and service boundary.
- Routed backend analysis through the workflow boundary for resume-match explanation, ATS suggestions, cover letter drafting, interview prep, and validation.
- Strengthened validation for cover letter unsupported skills and interview answer evidence IDs.
- Fixed local `OPENCLAW_SENDER_ALLOWLIST` environment parsing for comma-separated sender IDs.
- Added workflow and validator tests, increasing backend coverage from 11 to 14 tests.
- Updated backend and AI services documentation to describe the current deterministic fallback and future live CrewAI integration.
- Installed OpenClaw CLI with onboarding skipped and verified version `2026.6.11`.
- Added project-local OpenClaw workspace, `job` skill, and `resumepilot_job.py` helper around `/chat/openclaw`.
- Added OpenClaw setup docs and helper unit tests.
- Verified OpenClaw skill discovery/check and helper-to-backend smoke flow.
- Selected Google Vertex as the current OpenClaw model provider path and documented the gcloud ADC setup boundary.
- Implemented the initial Next.js WebChat/dashboard workbench in `Frontend/`.
- Added Next.js backend-for-frontend route handlers that proxy dashboard requests to FastAPI.
- Added frontend dependency lock, lint/typecheck/build scripts, and a PostCSS audit override for the Next.js dependency tree.
- Verified frontend audit, lint, typecheck, production build, backend tests, and live dashboard proxy smoke.
- Added the official CrewAI documentation URL as the required reference before live CrewAI implementation.
- Added OpenClaw Google Vertex configure/start scripts and an ignored local Gateway env flow.
- Updated Vertex defaults to `LLM_PROVIDER=vertex`, `VERTEX_REGION=global`, and `LLM_MODEL=gemini-3.5-flash`.
- Added backend settings coverage for the canonical Vertex env names.
- Switched the OpenClaw demo model default to `google-vertex/gemini-3.5-flash` after live Vertex validation.
- Ignored local OpenClaw workspace bootstrap/state files generated during Gateway startup.
- Extended the dashboard OpenClaw status route/card with live Gateway reachability and updated local commands.
- Verified Vertex ADC direct model access and documented the remaining OpenClaw local device pairing blocker.
- Added a guarded OpenClaw CLI device pairing repair script and used it to resolve the local scope-upgrade loop.
- Verified `openclaw agent` can execute `/job paste:...` through the running Gateway with Vertex `gemini-3.5-flash`.
- Verified current official CrewAI docs for typed direct agent kickoff and Python runtime support before live workflow implementation.
- Added an optional live CrewAI structured-output adapter behind `AGENT_WORKFLOW_MODE=crewai`.
- Added safe deterministic fallback with a `crewai_unavailable` warning for missing CrewAI, unsupported Python, or incomplete provider config.
- Added backend settings, docs, optional dependency extra, and tests for CrewAI mode success/fallback behavior.
- Corrected the CrewAI optional dependency to `crewai[google-genai]` for the native Google Gen AI provider.
- Created the ignored Python 3.12 verification environment at `Backend/.local/venvs/py312` and installed `.[dev,ai]`.
- Verified live CrewAI + Vertex execution with trace mode `crewai`, no fallback warning, and successful FastAPI upload/analyze/report HTTP flow.
- Added persisted analysis workflow trace metadata with an Alembic migration and report trace response schema.
- Exposed `GET /reports/{report_id}/trace` in FastAPI and the matching Next.js dashboard proxy route.
- Added a dashboard workflow trace panel for deterministic fallback versus live CrewAI execution status.
- Added backend API tests for deterministic trace persistence, CrewAI unavailable fallback persistence, and mocked CrewAI success persistence.
- Verified backend tests, lint, compile, migration, golden evals, frontend lint/typecheck/build, and the same-origin dashboard trace proxy smoke.
- Added `.python-version` and constrained backend package support to Python `>=3.12,<3.14`.
- Added Python 3.12 dev+AI dependency constraints and the `bootstrap_py312.sh` setup script.
- Recreated `Backend/.venv` with Python 3.12.13 and verified tests, lint, compile, migration, golden evals, and `pip check`.
- Added guarded local PDF compilation from generated LaTeX with `tectonic --untrusted` preference, `pdflatex -no-shell-escape` fallback, timeout limits, output-size limits, and no shell invocation.
- Added `GET /reports/{report_id}/resume/pdf` in FastAPI and the matching Next.js `/api/reports/[reportId]/resume/pdf` proxy route.
- Added a dashboard PDF download action beside Markdown and LaTeX exports.
- Added compiler, API, and settings tests for PDF export success, missing compiler handling, command safety, and output-size enforcement.
- Updated README files, MVP docs, security notes, testing docs, and this context file for the new PDF export behavior.
- Verified backend tests/lint/compile/golden evals/quality gate, frontend lint/typecheck/build, real `tectonic` compilation, and same-origin dashboard PDF proxy smoke.
- Added Playwright browser smoke testing for the dashboard upload/analyze/report/export flow.
- Added frontend e2e scripts, Playwright config, desktop/mobile screenshot capture, and ignored local browser test artifacts.
- Updated root/frontend README files, testing docs, tech-stack docs, and this context file with the Playwright browser smoke workflow.
- Verified Playwright Chromium install, frontend lint/typecheck, dashboard e2e smoke, backend tests, backend quality gate, and clean e2e smoke ports.
- Added backward-compatible workflow trace `duration_ms` telemetry for total and per-step latency across deterministic fallback, live CrewAI success, and CrewAI fallback paths.
- Rendered workflow trace timing in the dashboard and added backend/API/Playwright assertions for timing presence.
- Updated backend/frontend README files, MVP architecture/reliability/testing docs, and this context file for trace timing telemetry.
- Added live runtime provider observability fields to workflow traces for provider, model, token usage, cost estimate, and runtime metadata.
- Extracted CrewAI token usage from the live LLM summary when available and persisted it through the existing report trace JSON.
- Rendered runtime provider/model/token/cost metadata in the dashboard workflow trace panel.
- Updated backend/frontend README files, MVP architecture/reliability/testing docs, and this context file for runtime observability.
- Verified current Google pricing references for Gemini 3.5 Flash input, text output, and cached input rates before adding provider cost estimates.
- Added versioned Vertex/global `google/gemini-3.5-flash` provider pricing data and a strict backend pricing calculator.
- Wired pricing-backed `cost_estimate_usd` and pricing metadata into live CrewAI workflow traces when captured token usage is available.
- Added focused pricing, workflow, and API tests, increasing backend coverage from 29 to 34 tests.
- Updated backend/frontend README files, MVP docs, and this context file for pricing-backed runtime observability.

## Maintenance Rule

Update this file after every meaningful project change. Keep entries concise and factual:

- Update `Current Workspace State` when repo structure, tooling, runtime, or git status changes.
- Update `Selected MVP Tech Stack` only when a technology decision changes.
- Update `Build Order` or `Near-Term Implementation Scope` when sequencing changes.
- Update `Known Gaps` when a gap is resolved or a new blocker appears.
- Add one dated `Change Log` bullet for every implementation, documentation, dependency, test, or configuration change.

## Commit Message Rule

Use a concise subject plus a short body for implementation commits:

- Subject: clear action summary, usually under 72 characters.
- Body: 2-3 bullets explaining the important changes and why they matter.
- Keep commit bodies factual and compact; avoid generic messages such as "update files" or overly tiny summaries.
