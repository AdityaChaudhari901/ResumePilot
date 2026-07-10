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
optional CrewAI/ChromaDB dependency tree because CrewAI 1.15.2 constrains
ChromaDB to the affected 1.1.x line for `CVE-2026-45829`
(`https://osv.dev/vulnerability/PYSEC-2026-311`). ChromaDB 1.5.9 contains the
upstream fix, but it is outside CrewAI's current compatible range. ResumePilot
does not run a ChromaDB server, and excluding the unused package keeps the
default image's attack surface smaller.

Regenerate the production locks with the commands recorded in their generated
headers, review the diff, and rebuild the image before deployment.
