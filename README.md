# ResumePilot

ResumePilot is organized into four implementation areas:

- `Frontend/` - Next.js dashboard and authenticated backend-for-frontend proxy routes.
- `Backend/` - FastAPI API/worker, deterministic parsing, matching, claim validation,
  accepted-draft exports, durable operations, tests, migrations, and evals.
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

## Production Docker Baseline

Copy the example env file, replace every placeholder secret, then start the
PostgreSQL-backed stack:

```bash
cp .env.production.example .env.production
docker compose --env-file .env.production up --build
```

FastAPI exposes `/health` for liveness and `/ready` for database/migration
readiness. The backend refuses unsafe production startup, including SQLite,
missing signed-proxy auth, missing OpenClaw token, schema auto-creation, or
disabled migration checks.

The example binds FastAPI and Next.js to loopback and defaults to Clerk auth.
Put an HTTPS reverse proxy in front of Next.js, keep FastAPI private, and follow
the remaining release boundaries in the deployment runbook.

Read [Docs/DEPLOYMENT.md](Docs/DEPLOYMENT.md) before using this outside local
development.

## CI

GitHub Actions runs `.github/workflows/ci.yml` on pushes and pull requests to
`main`.

- Backend job: Python 3.12, hash-locked production dependency audit, Ruff,
  pytest, compileall, golden evals, and the deterministic quality gate.
- Frontend job: Node.js 24, `npm ci`, dependency audit, ESLint, typecheck,
  auth-runtime checks, and a production build.
- Browser job: a clean Next.js build, Chromium workflow/export coverage,
  security-header assertions, WCAG A/AA checks, and retained failure evidence.
- Deployment job: Compose validation plus backend/frontend container builds.

Live Vertex/CrewAI smokes remain local/manual because CI has no provider secret.
The default production image excludes the CrewAI/ChromaDB dependency tree because
CrewAI 1.15.2 constrains ChromaDB to the affected 1.1.x line; patched ChromaDB
1.5.9 is outside that compatibility range.

The backend runtime is standardized on Python 3.12 because live CrewAI execution
does not currently support Python 3.14.
