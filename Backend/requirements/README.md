# Backend Dependency Locks

`py312-dev-ai.constraints.txt` pins the resolved Python 3.12 dependency set for
the backend `dev` and `ai` extras. Use it as a constraints file with the editable
project install:

```bash
python -m pip install -e ".[dev,ai]" -c requirements/py312-dev-ai.constraints.txt
```

The canonical local setup is:

```bash
scripts/bootstrap_py312.sh --recreate
```

Regenerate the constraints only after intentionally changing backend dependency
ranges in `pyproject.toml` or upgrading the live CrewAI/Vertex runtime.
