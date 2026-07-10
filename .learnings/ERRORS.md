# ResumePilot Operational Errors

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
