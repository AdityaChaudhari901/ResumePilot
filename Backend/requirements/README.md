# Backend Dependency Locks

`py312-dev.constraints.txt` pins the resolved Python 3.12 dependency set for
the backend and its `dev` extra. Use it with the editable project install:

```bash
python -m pip install -e ".[dev]" -c requirements/py312-dev.constraints.txt
```

The canonical local setup is:

```bash
scripts/bootstrap_py312.sh --recreate
```

Regenerate the constraints only after intentionally changing backend dependency
ranges in `pyproject.toml` or upgrading the LangGraph/LangChain Vertex runtime.

The default production image uses `py312-build.lock.txt` and
`py312-production.lock.txt` with `pip --require-hashes`. The production lock
contains FastAPI, LangGraph, LangChain model primitives, the Google GenAI
integration, and the PostgreSQL checkpointer. CrewAI and ChromaDB are absent.
The production worker stores only internal IDs and redacted draft proposals in
checkpoints; raw resume text, contact data, provider secrets, and job text stay
in ResumePilot's tenant-scoped tables.

Regenerate the production locks with the commands recorded in their generated
headers, review the diff, and rebuild the image before deployment.
