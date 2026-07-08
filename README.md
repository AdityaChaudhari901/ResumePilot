# ResumePilot

ResumePilot is organized into four implementation areas:

- `Frontend/` - Next.js dashboard and backend-for-frontend proxy routes.
- `Backend/` - FastAPI backend, deterministic parsing, matching, validation, report exports, tests, migrations, and evals.
- `Ai services/` - OpenClaw local skill workspace and AI workflow support.
- `Docs/` - MVP documentation pack and supporting docs.

Read `Context.md` before making changes. Update it after every meaningful implementation, test, dependency, documentation, or configuration change.

## Current Working Areas

The active implementation spans `Backend/`, `Frontend/`, and `Ai services/`.

```bash
cd Backend
scripts/bootstrap_py312.sh --recreate
source .venv/bin/activate
pytest
python scripts/run_backend_quality_gate.py
```

Frontend browser smoke:

```bash
cd Frontend
npm run test:e2e:install
npm run test:e2e
```

## CI

GitHub Actions runs `.github/workflows/ci.yml` on pushes and pull requests to
`main`.

- Backend job: Python 3.12, pip constrained install, ruff format/check, pytest,
  compileall, golden evals, deterministic backend quality gate, and backend
  quality-gate artifact upload.
- Frontend job: Node.js 24, `npm ci`, ESLint, and TypeScript typecheck.

Live Vertex/CrewAI smokes and Playwright browser screenshots remain explicit
local/manual gates until provider secrets and browser artifacts are configured
for CI.

The backend runtime is standardized on Python 3.12 because live CrewAI execution
does not currently support Python 3.14.
