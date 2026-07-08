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
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```
