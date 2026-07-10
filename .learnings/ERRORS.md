# ResumePilot Operational Errors

## [ERR-20260710-009] langgraph-start-replayed-paid-model-nodes

**Logged**: 2026-07-10T08:48:01Z
**Priority**: high
**Status**: resolved
**Area**: reliability

### Summary

Calling `LiveDraftGraphRunner.start()` again for an operation that had already
reached its approval interrupt created a new graph turn and reran all three
model nodes.

### Error

```text
first start model calls: 3
retry start model calls: 3
```

### Context

- Reproduced with PostgreSQL after closing and reopening the checkpointer pool.
- This is the worker-crash window between persisting the LangGraph interrupt
  and marking the business operation as `waiting_for_approval`.
- The duplicate calls could add latency and provider cost even though usage
  metering remains keyed to one operation.

### Suggested Fix

Inspect and validate the existing thread snapshot before initial invocation.
Return an existing interrupt unchanged, resume only an incomplete checkpoint,
and reject mismatched operation, analysis, or graph-state versions.

### Metadata

- Reproducible: yes
- Related Files: Backend/app/services/langgraph_workflow.py, Backend/tests/test_langgraph_workflow.py

### Resolution

- **Resolved**: 2026-07-10T08:48:01Z
- **Notes**: Added idempotent start recovery and a no-rerun regression test;
  PostgreSQL restart verification is rerun as executable proof.

---

## [ERR-20260710-010] backend-targeted-lint-missing-select-import

**Logged**: 2026-07-10T09:49:45Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

A new SQLAlchemy regression test used `select()` without importing it, so Ruff
stopped the targeted verification sequence before pytest ran.

### Error

```text
F821 Undefined name `select`
```

### Context

- The failure followed the intentional addition of an old-reservation quota test.
- Ruff caught the missing symbol before the test suite executed.

### Suggested Fix

Import `select` from SQLAlchemy in the test module and rerun formatting, lint,
and the targeted tests in that order.

### Metadata

- Reproducible: yes
- Related Files: Backend/tests/test_workflow_jobs.py

### Resolution

- **Resolved**: 2026-07-10T09:49:45Z
- **Notes**: Added the missing SQLAlchemy import before rerunning verification.

---

## [ERR-20260710-011] compose-inspection-missing-production-env-file

**Logged**: 2026-07-10T09:56:51Z
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary

The first Compose status/config check omitted the production environment file,
so interpolation failed before Docker inspected the running stack.

### Error

```text
POSTGRES_PASSWORD is missing a value: Set POSTGRES_PASSWORD in .env.production
```

### Context

- Production-like Compose commands require the ignored root `.env.production`.
- No secret value was printed or changed.

### Suggested Fix

Pass `--env-file .env.production` to production-like Compose inspection and
runtime commands.

### Metadata

- Reproducible: yes
- Related Files: docker-compose.yml, .env.production.example

### Resolution

- **Resolved**: 2026-07-10T09:56:51Z
- **Notes**: Reran the checks with the existing ignored production environment file.

---

## [ERR-20260710-012] postgres-migration-gate-has-no-help-mode

**Logged**: 2026-07-10T09:57:19Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

Invoking the PostgreSQL migration gate with `--help` executed the gate instead
of showing usage and stopped because its required admin URL was absent.

### Error

```text
RuntimeError: POSTGRES_ADMIN_URL is required
```

### Context

- `run_postgres_migration_gate.py` is an environment-driven script, not an
  argparse command.
- The failure occurred before a database connection or mutation.

### Suggested Fix

Read the script entry contract and provide `POSTGRES_ADMIN_URL` in an isolated
PostgreSQL environment; do not assume a `--help` interface.

### Metadata

- Reproducible: yes
- Related Files: Backend/scripts/run_postgres_migration_gate.py

### Resolution

- **Resolved**: 2026-07-10T09:57:19Z
- **Notes**: Ran the gate inside the Compose network using the container's existing database URL and temporary gate databases.

---

## [ERR-20260710-013] staged-diff-markdown-trailing-whitespace

**Logged**: 2026-07-10T10:07:18Z
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary

The staged diff check rejected two Markdown header lines that used trailing
spaces for hard line breaks.

### Error

```text
Docs/project-audit/00-executive-summary.md:3-4: trailing whitespace
```

### Context

- The issue was caught before commit.
- It affected formatting only, not rendered content or application behavior.

### Suggested Fix

Use normal Markdown line breaks in audit metadata and rerun the staged diff
check before committing.

### Metadata

- Reproducible: yes
- Related Files: Docs/project-audit/00-executive-summary.md

### Resolution

- **Resolved**: 2026-07-10T10:07:18Z
- **Notes**: Removed the trailing spaces and restaged the corrected files.

---

## [ERR-20260710-008] langgraph-tables-crossed-alembic-ownership-boundary

**Logged**: 2026-07-10T08:48:01Z
**Priority**: high
**Status**: resolved
**Area**: database

### Summary

The PostgreSQL migration gate created LangGraph's package-owned checkpoint
tables before running `alembic check`, so Alembic treated all four tables as
schema drift and proposed removing them.

### Error

```text
New upgrade operations detected: remove checkpoint_migrations, checkpoints,
checkpoint_blobs, and checkpoint_writes
```

### Context

- Alembic owns ResumePilot business tables.
- `PostgresSaver.setup()` independently owns and migrates checkpoint tables.
- The migration gate correctly exposed the conflict on a fresh PostgreSQL 16
  database before release.

### Suggested Fix

Exclude reflected LangGraph checkpoint tables and their indexes from Alembic
autogeneration while continuing to verify their presence through the dedicated
checkpointer setup and readiness gates.

### Metadata

- Reproducible: yes
- Related Files: Backend/migrations/env.py, Backend/scripts/run_postgres_migration_gate.py

### Resolution

- **Resolved**: 2026-07-10T08:48:01Z
- **Notes**: Added an explicit Alembic ownership filter; the PostgreSQL gate is
  rerun as the executable proof.

---

## [ERR-20260710-001] frontend-check-node-path

**Logged**: 2026-07-10T07:36:28Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The outer zsh did not expose the project Node 24 installation, so a direct `npm run typecheck` invocation failed.

### Error

```text
zsh:1: command not found: npm
```

### Context

- Command attempted from `Frontend/`: `npm run typecheck`
- The project already documents Node.js v24.16.0 under `$HOME/.nvm/versions/node/v24.16.0/bin`.
- A login-shell invocation still did not source NVM, so `login: true` alone is not sufficient.
- The outer shell also has no `python` alias; repository automation should use `Backend/.venv/bin/python` explicitly.

### Suggested Fix

Prefix frontend verification commands explicitly with `PATH="$HOME/.nvm/versions/node/v24.16.0/bin:$PATH"` and use `Backend/.venv/bin/python` for repository Python automation.

### Metadata

- Reproducible: yes
- Related Files: Context.md, Frontend/package.json

### Resolution

- **Resolved**: 2026-07-10T07:37:30Z
- **Notes**: Explicitly prefixed the Node 24 binary directory; TypeScript verification passed.

---

## [ERR-20260710-007] retired-crewai-packages-conflicted-with-new-lock

**Logged**: 2026-07-10T14:12:00+05:30
**Priority**: low
**Status**: resolved
**Area**: config

### Summary

The existing development virtualenv retained CrewAI after the project moved to
the LangGraph dependency set, so `pip check` reported stale Pydantic conflicts.

### Error

```text
crewai 1.15.2 requires pydantic<2.13, but the new lock installs pydantic 2.13.4.
```

### Context

- Command: `.venv/bin/python -m pip install -e '.[dev]' -c requirements/py312-dev.constraints.txt`
- The generated constraints and production lock contained no CrewAI package.
- The conflict came from packages left in the pre-migration virtualenv.

### Suggested Fix

Recreate the virtualenv after removing an optional dependency family, or remove
the retired top-level packages before running `pip check`.

### Metadata

- Reproducible: yes
- Related Files: Backend/pyproject.toml, Backend/requirements/py312-dev.constraints.txt

### Resolution

- **Resolved**: 2026-07-10T14:13:00+05:30
- **Notes**: Removed `crewai`, `crewai-cli`, and `crewai-core`; `pip check` passed.

---

## [ERR-20260710-005] sqlite-datetime-timezone-roundtrip

**Logged**: 2026-07-10T07:57:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

SQLite returned a persisted UTC workflow heartbeat as a naive `datetime`, so a
direct equality assertion against the aware UTC input failed.

### Error

```text
datetime(..., tzinfo=None) != datetime(..., tzinfo=timezone.utc)
```

### Context

- Production uses PostgreSQL; the focused unit test uses SQLite.
- The stored instant and microseconds were otherwise identical.

### Suggested Fix

Normalize SQLite test values to UTC before comparing timezone-aware instants.

### Metadata

- Reproducible: yes
- Related Files: Backend/tests/test_workflow_jobs.py

### Resolution

- **Resolved**: 2026-07-10T07:58:00Z
- **Notes**: Normalized the two persisted lease timestamps in the assertion.

---

## [ERR-20260710-004] pip-audit-mutated-development-environment

**Logged**: 2026-07-10T08:05:00Z
**Priority**: medium
**Status**: resolved
**Area**: dependencies

### Summary

Installing `pip-audit` into the shared development virtual environment upgraded
CrewAI's constrained TOML dependencies and temporarily made `pip check` fail.

### Error

```text
crewai 1.15.2 requires tomli~=2.0.2, but tomli 2.4.1 was installed
```

### Context

- The production lock itself audited clean.
- The optional local AI environment contains ChromaDB 1.1.1 through CrewAI's
  `chromadb~=1.1.0` constraint and is intentionally excluded from production.

### Suggested Fix

Run dependency auditors in an isolated environment, and audit the production
lock directly instead of adding audit tooling to the application environment.

### Metadata

- Reproducible: yes
- Related Files: Backend/requirements/py312-production.lock.txt, Backend/requirements/README.md

### Resolution

- **Resolved**: 2026-07-10T08:08:00Z
- **Notes**: Audited the production lock with zero findings, restored the
  CrewAI-compatible TOML versions, removed `pip-audit`, and confirmed `pip check`.

---

## [ERR-20260710-003] nextjs-security-dependency-audit-help

**Logged**: 2026-07-10T07:48:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The bundled dependency audit shell script treats `--help` as a project directory instead of exposing help output.

### Error

```text
dependency-audit.sh: line 23: cd: --: invalid option
```

### Context

- The secret and pattern scanners expose normal `--help` interfaces.
- The dependency script expects the project path as its first positional argument.

### Suggested Fix

Invoke the dependency scanner with the frontend project path directly.

### Metadata

- Reproducible: yes
- Related Files: Frontend/package.json

### Resolution

- **Resolved**: 2026-07-10T07:48:00Z
- **Notes**: Continued with the documented positional project-path invocation.

---

## [ERR-20260710-002] postgres-migration-gate-baseline

**Logged**: 2026-07-10T07:45:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The expanded PostgreSQL head-index check also inspected the head-only `workflow_jobs` table after downgrade to the `0007` baseline.

### Error

```text
sqlalchemy.exc.NoSuchTableError: workflow_jobs
```

### Context

- The fresh and prior-version upgrades, Alembic drift checks, and queue-claim concurrency checks had passed.
- The failure occurred only in the baseline downgrade assertion after adding head-only indexes to the required index map.

### Suggested Fix

Skip head-only tables when validating which head-only indexes remain after a baseline downgrade.

### Metadata

- Reproducible: yes
- Related Files: Backend/scripts/run_postgres_migration_gate.py

### Resolution

- **Resolved**: 2026-07-10T07:45:00Z
- **Notes**: Baseline verification now ignores tables that correctly do not exist at `20260709_0007`.

---

## [ERR-20260710-006] privacy-test-normalized-job-text

**Logged**: 2026-07-10T08:00:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

Two privacy assertions compared persisted job text with the fixture's trailing
newline even though request validation intentionally normalizes surrounding
whitespace.

### Error

```text
AssertionError: persisted job_text omitted the fixture's trailing newline
```

### Context

- The stored content was otherwise identical and still contained the sensitive
  payload the cleanup test needed to prove was removed.
- The failure was in the test expectation, not the privacy implementation.

### Suggested Fix

Compare against the normalized fixture while retaining exact deletion and
post-deletion absence assertions.

### Metadata

- Reproducible: yes
- Related Files: Backend/tests/test_audit_privacy_api.py

### Resolution

- **Resolved**: 2026-07-10T08:00:00Z
- **Notes**: Updated the focused assertions to compare against stripped input.

---
