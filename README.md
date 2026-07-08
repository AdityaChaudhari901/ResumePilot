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

The backend runtime is standardized on Python 3.12 because live CrewAI execution
does not currently support Python 3.14.
