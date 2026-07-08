# ResumePilot

ResumePilot is organized into four implementation areas:

- `Frontend/` - future web dashboard.
- `Backend/` - FastAPI backend, deterministic parsing, matching, validation, reports, tests, migrations, and evals.
- `Ai services/` - future CrewAI and LLM workflow layer.
- `Docs/` - MVP documentation pack and supporting docs.

Read `Context.md` before making changes. Update it after every meaningful implementation, test, dependency, documentation, or configuration change.

## Current Working Area

The active implementation is in `Backend/`.

```bash
cd Backend
scripts/bootstrap_py312.sh --recreate
source .venv/bin/activate
pytest
```

The backend runtime is standardized on Python 3.12 because live CrewAI execution
does not currently support Python 3.14.
