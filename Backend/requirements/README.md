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

The default production image uses `py312-build.lock.txt` and
`py312-production.lock.txt` with `pip --require-hashes`. The production lock
contains the deterministic FastAPI runtime only. It deliberately excludes the
optional CrewAI/ChromaDB dependency tree until the unpatched ChromaDB
`CVE-2026-45829` server vulnerability
(`https://osv.dev/vulnerability/PYSEC-2026-311`) has a safe upstream release. ResumePilot
does not run a ChromaDB server, but excluding unused vulnerable code keeps the
default image's attack surface smaller.

Regenerate the production locks with the commands recorded in their generated
headers, review the diff, and rebuild the image before deployment.
