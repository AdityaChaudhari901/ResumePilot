# ResumePilot Operational Errors

## [ERR-20260711-015] case-overview-authority-edge-states

**Logged**: 2026-07-11T08:42:28Z
**Priority**: high
**Status**: resolved
**Area**: frontend

### Summary

The first case-overview pass treated score, draft, and source summary data as happy-path display
values instead of preserving their independent verification and provenance states.

### Error

```text
Code review: provisional or historical scores could receive current evidence labels; an unresolved
draft could show fabricated counts; an older deep link absent from the 20-item list could default
to URL provenance.
```

### Context

- The full report already had version-aware score authority, but the compact overview duplicated only the numeric-band logic.
- Tailored-resume ownership is verified by a separate protected request after report hydration.
- Route-hydrated application detail remains authoritative even when portfolio list data is absent.

### Suggested Fix

Centralize report score presentation, model draft lookup as loading/ready/unavailable, expose no
counts or resume route until IDs match, and use route-hydrated job source type.

### Metadata

- Reproducible: yes
- Related Files: Frontend/src/features/dashboard/utils/report.ts, Frontend/src/features/dashboard/components/report-viewer.tsx, Frontend/src/features/dashboard/components/application-case-overview.tsx, Frontend/src/features/dashboard/components/dashboard-shell.tsx, Frontend/e2e/dashboard.spec.ts

### Resolution

- **Resolved**: 2026-07-11T08:42:28Z
- **Notes**: Implemented all three fail-closed authority fixes and added a historical, missing-list, delayed-draft regression; the full 19-test browser suite passes.

---

## [ERR-20260711-014] case-bento-accessibility-contracts

**Logged**: 2026-07-11T08:27:04Z
**Priority**: medium
**Status**: resolved
**Area**: frontend

### Summary

The first browser pass found low contrast on the inverse-card validation badge and draft metrics
whose description-list items were not directly owned by a `<dl>`.

### Error

```text
axe: color-contrast, dlitem
```

### Context

- Semantic success colors were tuned for raised surfaces, not the graphite inverse decision card.
- The reusable metric emitted `dt`/`dd`; one caller used a generic grid container instead of a description list.

### Suggested Fix

Give inverse-card status text a high-contrast background/foreground pair and require every metric
group using `CaseMetric` to render as a `<dl>`.

### Metadata

- Reproducible: yes
- Related Files: Frontend/src/features/dashboard/components/application-case-overview.tsx, Frontend/e2e/dashboard.spec.ts

### Resolution

- **Resolved**: 2026-07-11T08:27:04Z
- **Notes**: Applied the inverse contrast override and corrected the draft metric container before rerunning Axe.

---

## [ERR-20260711-013] react-dynamic-milestone-icon

**Logged**: 2026-07-11T08:24:35Z
**Priority**: low
**Status**: resolved
**Area**: frontend

### Summary

The first bento milestone implementation selected a Lucide component inside render, which React's
static-component lint rule rejects because the component identity is recreated for each render.

### Error

```text
react-hooks/static-components: Cannot create components during render
```

### Context

- The milestone status helper returned a component type and the row rendered it through a local variable.
- TypeScript passed, but the React 19 lint gate correctly rejected the render pattern.

### Suggested Fix

Render each status branch from a statically declared `MilestoneStatusIcon` component.

### Metadata

- Reproducible: yes
- Related Files: Frontend/src/features/dashboard/components/application-case-overview.tsx

### Resolution

- **Resolved**: 2026-07-11T08:24:35Z
- **Notes**: Replaced render-time component selection with a static status component; lint and typecheck pass.

---

## [ERR-20260711-012] frontend-workdir-prefixed-root-path

**Logged**: 2026-07-11T08:22:57Z
**Priority**: medium
**Status**: resolved
**Area**: developer tooling

### Summary

A verification command entered `Frontend/` and then addressed a source file through a second
`Frontend/` prefix, so the inspection step stopped before typechecking.

### Error

```text
sed: Frontend/src/features/dashboard/components/dashboard-shell.tsx: No such file or directory
```

### Context

- The command combined source inspection and `npm run typecheck` from the frontend working directory.
- No source file or application state was changed by the failed read.

### Suggested Fix

Keep repository-relative source inspection in the repository root, then run package commands in a
separate call with `Frontend/` as the working directory.

### Metadata

- Reproducible: yes
- Related Files: Frontend/src/features/dashboard/components/dashboard-shell.tsx, Frontend/package.json

### Resolution

- **Resolved**: 2026-07-11T08:22:57Z
- **Notes**: Split repository inspection from frontend package verification and resumed from the correct working directories. The same prefix error recurred during the live Compose smoke, so stack commands now run only from the repository root and package commands run separately from `Frontend/`.

---

## [ERR-20260711-011] zsh-live-probe-used-reserved-variable-names

**Logged**: 2026-07-11T05:17:26Z
**Priority**: low
**Status**: resolved
**Area**: release verification

### Summary

A combined live HTTP probe used zsh's special `path` and read-only `status`
variables, which removed `curl` from command lookup before the route checks.

### Suggested Fix

Use neutral shell names such as `route_path` and `http_code` in zsh release
scripts, then rerun the complete probe rather than treating it as an app error.

### Resolution

- **Resolved**: 2026-07-11T05:17:26Z
- **Notes**: Reran the probe with safe names; all routes returned 200 and the live revision, index, containers, and worker were verified.

---

## [ERR-20260711-010] provenance-migration-validated-after-sqlite-ddl

**Logged**: 2026-07-10T20:03:49Z
**Priority**: high
**Status**: resolved
**Area**: database migration

### Summary

The first `0011` migration rejected duplicate active analyses only after adding
and backfilling `application_id`. SQLite can retain that DDL after the migration
fails, leaving revision `0010` with a partial `0011` schema that cannot retry.

### Suggested Fix

Derive and reject duplicate application provenance before any DDL, then prove a
blocked SQLite upgrade leaves the old schema intact and succeeds after draining.

### Resolution

- **Resolved**: 2026-07-10T20:03:49Z
- **Notes**: Moved duplicate detection ahead of the column addition and added a failed-upgrade/remediation/retry regression plus the PostgreSQL migration gate.

---

## [ERR-20260711-009] route-refresh-exposed-unhydrated-approval

**Logged**: 2026-07-10T20:03:49Z
**Priority**: high
**Status**: resolved
**Area**: frontend workflow integrity

### Summary

If a saved application detail, resume, or report request failed, Refresh could
still load its active operation and expose approval controls without verified
case evidence because the mutable hydrated application ID remained null.

### Suggested Fix

Use the route ID as authoritative mutation provenance, keep all route controls
locked until every protected dependency hydrates, and make Refresh retry both
status and route hydration.

### Resolution

- **Resolved**: 2026-07-10T20:03:49Z
- **Notes**: Added explicit hydration state, route-owned operation guards, locked recovery UI, and an E2E regression covering detail, resume, and report failures before a successful refresh.

---

## [ERR-20260711-008] application-analysis-single-active-race

**Logged**: 2026-07-10T20:03:49Z
**Priority**: high
**Status**: resolved
**Area**: workflow concurrency

### Summary

Two different idempotency keys could pass the application-level active check
concurrently and enqueue two analyses for the same tenant/application. The
first unique-index patch then surfaced the losing request as an unhandled 500.

### Suggested Fix

Enforce the invariant with a partial unique database index, translate the
losing write to an authoritative 409, and roll back its quota reservation.

### Resolution

- **Resolved**: 2026-07-10T20:03:49Z
- **Notes**: Added the partial index, typed conflict recovery, ambiguous-active fail-closed handling, API regressions, and a two-transaction PostgreSQL race gate.

---

## [ERR-20260711-007] routed-provenance-tests-used-pre-filter-contract

**Logged**: 2026-07-10T19:34:00Z
**Priority**: medium
**Status**: resolved
**Area**: browser regression coverage

### Summary

The first routed-provenance browser fixture returned an application-B operation
from an endpoint filtered for application A, then a canonical report redirect
left one helper scoped to the retired combined-workflow container.

### Error

```text
Run AI analysis remained disabled; later the report-id locator timed out.
```

### Context

- The client correctly failed closed on the impossible filtered response.
- The production report was visible on its canonical route, outside the old
  `Active workflow step` section.

### Suggested Fix

Make mocks honor authoritative query filters, test lookup failure separately,
and target route-owned content rather than retired page containers.

### Metadata

- Reproducible: yes
- Related Files: Frontend/e2e/dashboard.spec.ts

### Resolution

- **Resolved**: 2026-07-10T19:41:00Z
- **Notes**: Corrected the active-operation fixture, preserved the fail-closed warning, and updated the report locator; focused desktop/mobile flows pass.

---

## [ERR-20260711-006] workflow-provenance-derived-from-immutable-request

**Logged**: 2026-07-10T19:23:00Z
**Priority**: high
**Status**: resolved
**Area**: workflow state integrity

### Summary

The first application-provenance patch read only the immutable analysis request.
Raw URL/text workflows create their application during finalization, so paused
operations still returned a null application ID and could not be approved after
the frontend inferred the newly created case file.

### Error

```text
waiting_for_approval operation application_id=None while application 1 existed
```

### Context

- Adding the generated ID back into the executable request would invalidate
  retries because `application_id` cannot be combined with raw job input.
- Active lookup also depended on the newest 20 generic operations and failed open.

### Suggested Fix

Persist authoritative application provenance separately, set it atomically in
analysis finalization, and query active operations through a filtered endpoint.

### Metadata

- Reproducible: yes
- Related Files: Backend/app/db/models.py, Backend/app/services/analysis_finalization_service.py, Frontend/src/features/dashboard/components/dashboard-shell.tsx

### Resolution

- **Resolved**: 2026-07-10T19:38:00Z
- **Notes**: Added migration 20260711_0011, raw-workflow/list/get coverage, filtered active lookup, fail-closed UI state, and isolated unlinked recovery.

---

## [ERR-20260711-005] operation-provenance-guard-ruff-sim114

**Logged**: 2026-07-10T19:18:00Z
**Priority**: low
**Status**: resolved
**Area**: backend quality gate

### Summary

The first workflow-operation provenance guard used two branches that assigned
the same fallback, which Ruff rejected under `SIM114`.

### Error

```text
SIM114 Combine if branches using logical or operator
```

### Context

- The validation correctly rejected booleans, non-integers, and non-positive IDs.
- The failure was structural and occurred before the focused regression test ran.

### Suggested Fix

Combine the invalid-value predicates into one short-circuiting condition.

### Metadata

- Reproducible: yes
- Related Files: Backend/app/services/workflow_job_service.py

### Resolution

- **Resolved**: 2026-07-10T19:19:00Z
- **Notes**: Consolidated the predicates and reran Ruff before the regression test.

---

## [ERR-20260711-004] mobile-test-used-retired-summary-action

**Logged**: 2026-07-10T19:00:23Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The routed mobile E2E scenario still waited for the retired same-page “Open
tailored resume draft” summary action after the helper had moved to the
canonical application report URL.

### Error

```text
locator.click: waiting for button Open tailored resume draft
```

### Context

- All other fifteen browser scenarios passed.
- The report route correctly exposes “Review tailored resume,” which navigates
  to the application-scoped resume approval page.

### Suggested Fix

Use the report action and assert the canonical `/app/applications/[id]/resume`
route before checking accepted-draft exports.

### Metadata

- Reproducible: yes
- Related Files: Frontend/e2e/dashboard.spec.ts

### Resolution

- **Resolved**: 2026-07-10T19:00:23Z
- **Notes**: Updated the mobile route transition and URL assertion.

---

## [ERR-20260711-003] mobile-workflow-rail-keyboard-access

**Logged**: 2026-07-10T18:57:27Z
**Priority**: medium
**Status**: resolved
**Area**: frontend

### Summary

The first routed Playwright pass found that the horizontally scrollable mobile
workflow rail could not receive keyboard focus in Safari-compatible semantics.

### Error

```text
scrollable-region-focusable: Scrollable region must have keyboard access
```

### Context

- Fifteen of sixteen browser scenarios passed.
- The failure appeared in the WCAG A/AA scan at the 390 px workflow viewport.

### Suggested Fix

Make the labeled workflow region focusable so keyboard users can scroll it,
while retaining the ordered-list progress semantics.

### Metadata

- Reproducible: yes
- Related Files: Frontend/src/features/dashboard/components/workflow-progress.tsx

### Resolution

- **Resolved**: 2026-07-10T18:57:27Z
- **Notes**: Added keyboard focusability to the scrollable workflow region.

---

## [ERR-20260711-002] route-hydration-effect-synchronous-state

**Logged**: 2026-07-10T18:52:00Z
**Priority**: low
**Status**: resolved
**Area**: frontend

### Summary

The first multi-route lint pass rejected a synchronous loading-state update in
the route hydration effect and found two unused overview icons.

### Error

```text
react-hooks/set-state-in-effect: Avoid calling setState() directly within an effect
```

### Context

- TypeScript passed in the same verification run.
- The loading state was already initialized correctly from the route props, so
  the effect update was redundant.

### Suggested Fix

Let the state initializer cover routes without IDs, keep effect updates inside
the asynchronous hydration path, and remove unused imports.

### Metadata

- Reproducible: yes
- Related Files: Frontend/src/features/dashboard/components/dashboard-shell.tsx, Frontend/src/features/dashboard/components/workspace-overview.tsx

### Resolution

- **Resolved**: 2026-07-10T18:52:00Z
- **Notes**: Removed the redundant state update and unused imports before rerunning lint.

---

## [ERR-20260711-001] frontend-agent-shared-guidance-still-missing

**Logged**: 2026-07-10T18:34:18Z
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary

The installed `frontend-agent` skill still references shared protocol files
that are absent from its installation, so its optional preparation checklist
cannot be read in full.

### Error

```text
wc: /Users/adityachaudhari/.codex/skills/_shared/difficulty-guide.md: open: No such file or directory
```

### Context

- Recurred while preparing the multi-route ResumePilot interface redesign.
- The skill's own execution protocol, checklist, examples, and Tailwind rules
  remain available and were read completely.

### Suggested Fix

Repair the installed `frontend-agent` package so its referenced `_shared`
resources ship with the skill, or remove those stale references.

### Metadata

- Reproducible: yes
- Related Files: none
- See Also: ERR-20260710-018

### Resolution

- **Resolved**: 2026-07-10T18:34:18Z
- **Notes**: Continued with the available skill resources plus repository-specific conventions.

---

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

## [ERR-20260710-044] next-rsc-prefetch-smoke-false-positive

**Logged**: 2026-07-10T19:19:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The production browser smoke classified a cancelled Next.js RSC prefetch as a
failed static asset even though the page rendered with no HTTP error response.

### Error

```text
requestfailed: /?_rsc=...
```

### Context

- The document rendered the expected workflow heading, correct font, and no
  horizontal overflow.
- Next.js may cancel speculative RSC requests as navigation settles.
- With no stored override, dark mode is intentionally selected by the CSS
  system-preference media query rather than a `data-theme` attribute.

### Suggested Fix

Record failure reasons and treat `net::ERR_ABORTED` speculative requests as
non-actionable while continuing to fail on HTTP 4xx/5xx and other network
errors. Verify effective `color-scheme` instead of requiring a theme marker.

### Metadata

- Reproducible: yes
- Related Files: Frontend/public/theme-init.js, Frontend/src/app/globals.css

### Resolution

- **Resolved**: 2026-07-10T19:19:00Z
- **Notes**: Refined the smoke to inspect failure reasons and computed theme state.

---

## [ERR-20260710-043] host-node-missing-from-path

**Logged**: 2026-07-10T19:17:00Z
**Priority**: low
**Status**: resolved
**Area**: developer tooling

### Summary

The final Playwright smoke could not start because the non-interactive host
shell did not expose the installed Node binary on `PATH`.

### Error

```text
zsh: command not found: node
```

### Context

- The application and Compose containers remained healthy.
- The frontend build and earlier E2E suite had already completed in their
  configured environments.

### Suggested Fix

Resolve and prepend the workstation's managed Node installation path before
running host-side Playwright commands.

### Metadata

- Reproducible: yes
- Related Files: none

### Resolution

- **Resolved**: 2026-07-10T19:17:00Z
- **Notes**: Used the installed managed Node binary explicitly for the smoke.

---

## [ERR-20260710-042] zsh-status-readonly-health-probe

**Logged**: 2026-07-10T19:14:00Z
**Priority**: low
**Status**: resolved
**Area**: developer tooling

### Summary

A Compose health polling helper assigned to `status`, which is a read-only
special parameter in zsh, so the helper exited before evaluating the container.

### Error

```text
zsh: read-only variable: status
```

### Context

- The frontend container had already restarted successfully.
- Only the local verification helper failed.

### Suggested Fix

Use a non-special name such as `health_state` in cross-shell verification
snippets.

### Metadata

- Reproducible: yes
- Related Files: none

### Resolution

- **Resolved**: 2026-07-10T19:14:00Z
- **Notes**: Renamed the helper variable and reran the health probe.

---

## [ERR-20260710-041] next-docker-public-assets-missing

**Logged**: 2026-07-10T19:10:00Z
**Priority**: high
**Status**: resolved
**Area**: deployment

### Summary

The production Next.js container served application routes but returned 404 for
the pre-hydration theme script because the runtime image did not copy `public/`.

### Error

```text
GET /theme-init.js 404
```

### Context

- Local builds and Playwright runs served the asset correctly.
- The failure appeared only after rebuilding and probing the Compose runtime.

### Suggested Fix

Copy `/app/public` from the builder stage into the frontend runtime image and
retain an HTTP asset probe in production verification.

### Metadata

- Reproducible: yes
- Related Files: Frontend/Dockerfile, Frontend/public/theme-init.js

### Resolution

- **Resolved**: 2026-07-10T19:10:00Z
- **Notes**: Added the missing runtime-stage `public/` copy and rebuilt the image.

---

## [ERR-20260710-020] openclaw-backend-venv-relative-path

**Logged**: 2026-07-10T16:05:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The OpenClaw verification command addressed the backend virtual environment
from the wrong parent directory.

### Error

```text
zsh:1: no such file or directory: ../Backend/.venv/bin/python
```

### Context

- The command ran from `Ai services/openclaw`, where the repository backend is
  two directory levels up rather than one.
- No OpenClaw test or source code ran before the shell rejected the path.

### Suggested Fix

Use `../../Backend/.venv/bin/python` from the OpenClaw package directory, or an
absolute repository-root path.

### Metadata

- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution

- **Resolved**: 2026-07-10T16:05:00Z
- **Notes**: Re-ran the OpenClaw tests and compile check with the correct path.

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

## [ERR-20260710-014] analysis-finalization-partial-commit-reproduction

**Logged**: 2026-07-10T10:21:25Z
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary

Fault-injection and legacy-replay regressions confirmed that analysis completion
can persist without all linked application, audit, and usage state.

### Error

```text
Post-application audit failure left a completed analysis committed.
Completed-analysis replay returned success without recreating its application.
```

### Context

- A simulated `job.analyzed` audit failure occurred after the current analysis
  and application commits.
- A completed durable analysis was replayed after its downstream application and
  analysis audit events were removed.
- Both tests intentionally fail against the pre-fix implementation.

### Suggested Fix

Stage completed analysis state, application linkage, idempotent analysis audit
events, and usage settlement in one transaction. On completed-analysis replay,
run the same finalizer before returning.

### Metadata

- Reproducible: yes
- Related Files: Backend/app/services/analysis_service.py, Backend/app/services/application_service.py, Backend/tests/test_workflow_jobs.py

### Resolution

- **Resolved**: 2026-07-10T10:40:00Z
- **Notes**: One row-locked finalizer now commits analysis, application, audits, and usage together; replay, post-commit crash, supersession, stale-worker, OpenClaw, and PostgreSQL concurrency gates pass.

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

## [ERR-20260710-015] zsh-health-check-reserved-status-variable

**Logged**: 2026-07-10T10:37:17Z
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary

The Compose health polling wrapper assigned to zsh's read-only `status` variable.

### Error

```text
zsh:1: read-only variable: status
```

### Context

- The backend and worker containers had restarted successfully.
- Only the follow-up polling command failed before issuing health requests.

### Suggested Fix

Use a non-reserved variable such as `health_state` in zsh automation.

### Metadata

- Reproducible: yes
- Related Files: docker-compose.yml

### Resolution

- **Resolved**: 2026-07-10T10:37:17Z
- **Notes**: Reran the health poll with `health_state`; no application change was required.

---

## [ERR-20260710-016] playwright-started-with-incomplete-next-build

**Logged**: 2026-07-10T10:39:00Z
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary

The first Playwright release-gate run timed out because its interrupted frontend build left `.next` without `BUILD_ID`.

### Error

```text
Error: Timed out waiting 120000ms from config.webServer.
Error: Could not find a production build in the '.next' directory.
```

### Context

- The temporary FastAPI E2E server reached healthy state.
- A direct `next start` reproduced the missing production-build marker.
- No Playwright test had started, so this was a server-artifact failure rather than a product assertion failure.

### Suggested Fix

Regenerate the production build and confirm `.next/BUILD_ID` before rerunning the browser gate.

### Metadata

- Reproducible: yes
- Related Files: Frontend/playwright.config.ts, Frontend/package.json
- See Also: ERR-20260710-001

### Resolution

- **Resolved**: 2026-07-10T10:40:00Z
- **Notes**: A clean `npm run build` recreated `BUILD_ID`; the next Playwright run passed all 12 tests.

---

## [ERR-20260710-021] audit-doc-multi-file-patch-context

**Logged**: 2026-07-10T16:11:00Z
**Priority**: low
**Status**: resolved
**Area**: documentation

### Summary

A multi-file audit documentation patch used a paragraph fragment that did not
include the preceding words on the same wrapped source line.

### Error

```text
apply_patch verification failed: Failed to find expected lines
```

### Context

- The rendered paragraph looked equivalent, but the expected hunk began at
  `Several P1 defects` while the source line began at `the audit. Several`.
- `apply_patch` rejected the complete multi-file patch without partial edits.

### Suggested Fix

Inspect physical source lines and use smaller, uniquely anchored hunks for
multi-file documentation updates.

### Metadata

- Reproducible: yes
- Related Files: Docs/project-audit/00-executive-summary.md

### Resolution

- **Resolved**: 2026-07-10T16:11:00Z
- **Notes**: Split the documentation update into exact file-local patches.

---

## [ERR-20260710-022] matcher-test-import-order

**Logged**: 2026-07-10T16:22:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The focused matcher gate stopped because the new schema import followed service
imports.

### Error

```text
I001 Import block is un-sorted or un-formatted
```

### Context

- Ruff formatting does not reorder imports; Ruff lint caught the ordering before
  pytest started.
- No test executed in the failed command.

### Suggested Fix

Keep schema imports before service imports and run Ruff lint before the focused
pytest command.

### Metadata

- Reproducible: yes
- Related Files: Backend/tests/test_matcher.py

### Resolution

- **Resolved**: 2026-07-10T16:22:00Z
- **Notes**: Moved the schema import above service imports and reran the gate.

---

## [ERR-20260710-023] brooks-review-missing-shared-instructions

**Logged**: 2026-07-10T16:25:00Z
**Priority**: medium
**Status**: resolved
**Area**: tooling

### Summary

The installed `brooks-review` skill omits the shared files required by its setup
protocol.

### Error

```text
Missing ../_shared/common.md, source-coverage.md, and decay-risks.md
```

### Context

- `brooks-review/SKILL.md` requires all three shared files before the local
  `pr-review-guide.md` process can run.
- The package includes the review guide, but not the report template, source
  coverage rules, risk definitions, or severity thresholds.

### Suggested Fix

Repair the installed Brooks package so all skills ship the referenced `_shared`
directory.

### Metadata

- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution

- **Resolved**: 2026-07-10T16:25:00Z
- **Notes**: Used the available guide and independent focused reviewers as the
  fallback release review.

---

## [ERR-20260710-024] score-benchmark-case-count-assertion

**Logged**: 2026-07-10T16:32:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The quality-gate regression still expected six labeled score cases after the
monotonicity corpus grew.

### Error

```text
assert 8 == 6
```

### Context

- The gate evaluated the added cases successfully, then the test failed on its
  fixed corpus-size assertion.
- The corpus grew again to ten cases while correcting unknown-tenure semantics.

### Suggested Fix

Update the expected case count whenever the intentionally versioned labeled
corpus changes.

### Metadata

- Reproducible: yes
- Related Files: Backend/tests/test_backend_quality_gate.py, Backend/evals/match_score_cases.json

### Resolution

- **Resolved**: 2026-07-10T16:32:00Z
- **Notes**: Updated the expected corpus size to ten cases and reran the gate.

---

## [ERR-20260710-025] score-gate-debug-output-key

**Logged**: 2026-07-10T16:38:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

A diagnostic snippet assumed the score benchmark report stored cases under a
`cases` key.

### Error

```text
KeyError: 'cases'
```

### Context

- The quality gate had already printed the two useful band failures.
- The follow-up debug reader used the wrong internal output key and did not
  change source or evaluation data.

### Suggested Fix

Inspect the report keys before selecting optional diagnostic fields; use the
printed failure list when it already contains the exact scores and deltas.

### Metadata

- Reproducible: yes
- Related Files: Backend/evals/outputs/backend_quality_gate.json

### Resolution

- **Resolved**: 2026-07-10T16:38:00Z
- **Notes**: Adjusted the labeled bands from the gate's exact failure output and
  reran the benchmark.

---

## [ERR-20260710-026] rollback-sidecar-table-definition

**Logged**: 2026-07-10T16:43:00Z
**Priority**: medium
**Status**: resolved
**Area**: database

### Summary

The migration's lightweight `analyses` table definition omitted the breakdown
column used by the rollback restore update.

### Error

```text
sqlalchemy.exc.CompileError: Unconsumed column names: score_breakdown_json
```

### Context

- Fresh SQLite upgrade and downgrade completed; the re-upgrade failed before
  restoring any sidecar rows.
- SQLAlchemy validates update keys against the local migration table object.

### Suggested Fix

Declare every updated column on the lightweight migration table and exercise
both empty and populated downgrade/re-upgrade paths.

### Metadata

- Reproducible: yes
- Related Files: Backend/migrations/versions/20260710_0010_version_match_scores.py

### Resolution

- **Resolved**: 2026-07-10T16:43:00Z
- **Notes**: Added `score_breakdown_json` to the migration table definition and
  reran SQLite and PostgreSQL round trips.

---

## [ERR-20260710-017] brooks-test-missing-shared-instructions

**Logged**: 2026-07-10T15:26:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The installed `brooks-test` skill references shared instruction files that are
not present in the installed skills directory.

### Error

```text
wc: /Users/adityachaudhari/.codex/skills/_shared/common.md: open: No such file or directory
wc: /Users/adityachaudhari/.codex/skills/_shared/source-coverage.md: open: No such file or directory
wc: /Users/adityachaudhari/.codex/skills/_shared/test-decay-risks.md: open: No such file or directory
```

### Context

- The test-review skill requires those files to be read before use.
- A repository-wide filename search found no installed copies.
- The product implementation does not depend on the skill package.

### Suggested Fix

Repair the installed `brooks-test` package so it bundles its documented
`_shared` resources.

### Metadata

- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution

- **Resolved**: 2026-07-10T15:26:00Z
- **Notes**: Skipped the incomplete skill and used the repository's existing pytest conventions plus OneForAll testing guidance.

---

## [ERR-20260710-018] frontend-agent-missing-shared-protocol-files

**Logged**: 2026-07-10T15:38:00Z
**Priority**: low
**Status**: resolved
**Area**: frontend

### Summary

The installed `frontend-agent` skill references shared execution files that are
not included in its installed directory.

### Error

```text
resources/execution-protocol.md references ../_shared/difficulty-guide.md,
lessons-learned.md, clarification-protocol.md, context-budget.md, and
common-checklist.md, but the installed frontend-agent package has no _shared directory.
```

### Context

- The available execution protocol, component template, Tailwind rules, and
  frontend checklist were readable.
- The complete `frontend-ui-ux-copilot` references were also available.
- The missing package resources do not affect the ResumePilot source tree.

### Suggested Fix

Repair the installed `frontend-agent` package so its referenced `_shared`
resources ship with the skill.

### Metadata

- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution

- **Resolved**: 2026-07-10T15:38:00Z
- **Notes**: Continued with the available frontend-agent resources, project conventions, and complete UX-copilot guidance.

---

## [ERR-20260710-019] backend-pytest-run-from-repository-root

**Logged**: 2026-07-10T15:44:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

Running the backend suite from the repository root made the readiness test load
the wrong relative Alembic configuration path.

### Error

```text
alembic.util.exc.CommandError: No 'script_location' key found in configuration.
```

### Context

- Command: `Backend/.venv/bin/pytest -q Backend/tests` from the repository root.
- `test_ready_passes_after_alembic_upgrade` intentionally constructs
  `Config("alembic.ini")`, relative to the backend package root.
- The other 154 tests passed before this command-boundary failure.

### Suggested Fix

Run the complete backend suite from `Backend/` with `.venv/bin/pytest -q`.

### Metadata

- Reproducible: yes
- Related Files: Backend/tests/test_health.py, Backend/alembic.ini

### Resolution

- **Resolved**: 2026-07-10T15:44:00Z
- **Notes**: Re-ran the release suite from the documented backend working directory.

---

## [ERR-20260710-027] workflow-overrode-version-aware-score-copy

**Logged**: 2026-07-10T16:23:42Z
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary

The report generator used version-aware score wording, but the deterministic
agent workflow replaced that executive summary with generic score copy.

### Error

```text
AssertionError: deterministic_v1 executive summary did not contain
"legacy match score"
```

### Context

- The Markdown heading and disclaimer were already version-aware.
- The final workflow report overwrote the generator summary after match-agent
  execution, so historical v1 reports still received ambiguous copy.

### Suggested Fix

Test the final workflow-produced report for every supported scoring version,
not only the intermediate report generator output.

### Metadata

- Reproducible: yes
- Related Files: Backend/app/services/agent_workflow.py, Backend/tests/test_report_generator.py

### Resolution

- **Resolved**: 2026-07-10T16:23:42Z
- **Notes**: Made deterministic workflow summaries scoring-version aware and added a v1 regression test.

---

## [ERR-20260710-028] frontend-node-path-not-exported

**Logged**: 2026-07-10T16:40:00Z
**Priority**: low
**Status**: resolved
**Area**: frontend

### Summary

The non-interactive shell did not include the installed Node.js 24 binary, so
the first frontend lint command could not find `npm`.

### Error

```text
zsh:1: command not found: npm
```

### Context

- Node.js 24.16.0 is installed under both the user's NVM directory and the
  Homebrew `node@24` prefix.
- The project itself and its dependencies were unchanged.

### Suggested Fix

Export `/opt/homebrew/opt/node@24/bin` for non-interactive frontend commands.

### Metadata

- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution

- **Resolved**: 2026-07-10T16:40:00Z
- **Notes**: Re-ran frontend commands with the Node.js 24 Homebrew prefix in PATH.

---

## [ERR-20260710-029] compose-psql-status-query-quote-loss

**Logged**: 2026-07-10T16:59:25Z
**Priority**: low
**Status**: resolved
**Area**: deployment

### Summary

A nested shell command stripped the SQL string quotes around a display separator
while checking active workflow counts before the Compose upgrade.

### Error

```text
ERROR: syntax error at or near ":"
LINE 1: SELECT status || : || count(*) ...
```

### Context

- The query was read-only and did not change application or database state.
- The failure came from unnecessary nested quoting around a cosmetic separator.

### Suggested Fix

Select status and count as separate columns in nested Compose/psql commands.

### Metadata

- Reproducible: yes
- Related Files: .learnings/ERRORS.md, Docs/DEPLOYMENT.md

### Resolution

- **Resolved**: 2026-07-10T16:59:25Z
- **Notes**: Replaced the concatenated display expression with a plain two-column query.

---

## [ERR-20260710-030] shell-backtick-command-substitution-in-search

**Logged**: 2026-07-10T17:04:00Z
**Priority**: low
**Status**: resolved
**Area**: developer tooling

### Summary

A double-quoted ripgrep pattern containing Markdown backticks triggered shell
command substitution during a documentation consistency check.

### Error

```text
zsh:1: command not found: 20260710_0009
```

### Context

- The command was read-only and the remaining search still completed.
- Markdown backticks should not be placed unescaped inside double-quoted shell
  arguments.

### Suggested Fix

Use a single-quoted ripgrep pattern or omit literal backticks from the pattern.

### Metadata

- Reproducible: yes
- Related Files: .learnings/ERRORS.md, Context.md

### Resolution

- **Resolved**: 2026-07-10T17:04:00Z
- **Notes**: Re-ran consistency checks with single-quoted search patterns.

---

## [ERR-20260710-031] multi-file-patch-used-wrong-file-context

**Logged**: 2026-07-10T17:08:00Z
**Priority**: low
**Status**: resolved
**Area**: developer tooling

### Summary

An initial multi-file patch placed a test-file hunk under the matcher file and
failed its context verification without changing files.

### Error

```text
apply_patch verification failed: Failed to find expected lines in matcher.py
```

### Context

- The patch failed atomically before changing the working tree.
- The intended production, test, and benchmark edits spanned three files.

### Suggested Fix

Use an explicit file header before every hunk in a multi-file patch.

### Metadata

- Reproducible: yes
- Related Files: Backend/app/services/matcher.py, Backend/tests/test_matcher.py

### Resolution

- **Resolved**: 2026-07-10T17:08:00Z
- **Notes**: Reapplied the changes with explicit file boundaries and verified each result.

---

## [ERR-20260710-032] fontsource-variable-package-name-not-published

**Logged**: 2026-07-10T17:39:00Z
**Priority**: low
**Status**: resolved
**Area**: frontend

### Summary

The dependency lookup assumed IBM Plex Mono had a Fontsource variable-font
package, but that scoped package is not published.

### Error

```text
npm error 404 Not Found - GET https://registry.npmjs.org/@fontsource-variable%2fibm-plex-mono
```

### Context

- The failure occurred during a read-only npm registry lookup before the font
  dependency was installed.
- `@fontsource-variable/manrope` exists, while IBM Plex Mono must use its
  non-variable `@fontsource/ibm-plex-mono` package or a different mono family.

### Suggested Fix

Verify Fontsource package names with `npm view` before adding them, and use the
published non-variable IBM Plex Mono package when this font pairing is needed.

### Metadata

- Reproducible: yes
- Related Files: Frontend/package.json, .learnings/ERRORS.md

### Resolution

- **Resolved**: 2026-07-10T17:39:00Z
- **Notes**: Switched the planned dependency to the published non-variable package.

---

## [ERR-20260710-033] tailored-draft-style-patch-context-mismatch

**Logged**: 2026-07-10T17:55:00Z
**Priority**: low
**Status**: resolved
**Area**: frontend

### Summary

A combined styling patch expected an outdated TailoredResume metric class and
failed atomically before editing either target component.

### Error

```text
apply_patch verification failed: Failed to find expected lines in tailored-resume-workspace-card.tsx
```

### Context

- The helper used a `text-2xl` metric class while the patch expected `text-xl`.
- The failed patch also included approval-panel changes, but no hunk was applied.

### Suggested Fix

Inspect the exact helper context and split broad multi-file visual patches into
smaller file-scoped patches.

### Metadata

- Reproducible: yes
- Related Files: Frontend/src/features/dashboard/components/tailored-resume-workspace-card.tsx, Frontend/src/features/dashboard/components/workflow-approval-panel.tsx

### Resolution

- **Resolved**: 2026-07-10T17:55:00Z
- **Notes**: Re-read the live source and reapplied smaller exact-context patches.

---

## [ERR-20260710-034] theme-toggle-effect-state-lint

**Logged**: 2026-07-10T18:01:00Z
**Priority**: low
**Status**: resolved
**Area**: frontend

### Summary

The first theme-toggle implementation synchronously updated React state inside
an effect and failed the React 19 hooks lint rule.

### Error

```text
react-hooks/set-state-in-effect: Avoid calling setState() directly within an effect
```

### Context

- TypeScript passed; only the frontend lint gate failed.
- The effect was synchronizing persisted or system theme preference after hydration.

### Suggested Fix

Model browser theme preference with `useSyncExternalStore`, publish a local
theme-change event, and reserve the effect for synchronizing external DOM state.

### Metadata

- Reproducible: yes
- Related Files: Frontend/src/components/ui/theme-toggle.tsx

### Resolution

- **Resolved**: 2026-07-10T18:01:00Z
- **Notes**: Replaced effect-driven component state with a browser theme store subscription.

---

## [ERR-20260710-035] playwright-iphone-profile-required-webkit

**Logged**: 2026-07-10T18:06:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The standalone Playwright screenshot command selected WebKit for an iPhone
device profile, but only Chromium is installed in this frontend workspace.

### Error

```text
Executable doesn't exist at .../ms-playwright/webkit-2311/pw_run.sh
```

### Context

- The application build and desktop Chromium render both succeeded.
- The product E2E project is intentionally configured for Chromium.

### Suggested Fix

Use the installed Chromium executable with an explicit mobile viewport and
user agent instead of letting the screenshot CLI infer WebKit from an iPhone profile.

### Metadata

- Reproducible: yes
- Related Files: Frontend/playwright.config.ts

### Resolution

- **Resolved**: 2026-07-10T18:06:00Z
- **Notes**: Re-ran mobile visual checks in Chromium with explicit viewport sizes.

---

## [ERR-20260710-036] report-score-warning-badge-contrast

**Logged**: 2026-07-10T18:12:00Z
**Priority**: medium
**Status**: resolved
**Area**: frontend

### Summary

The semantic warning badge used its normal amber-on-tint treatment inside the
new inverted score panel and failed WCAG AA contrast in desktop and mobile E2E.

### Error

```text
color-contrast: #92530d on #232013, contrast 2.69, expected 4.5:1
```

### Context

- Eleven of thirteen Playwright scenarios passed.
- Both failures came from the same `Partial evidence coverage` badge after the
  completed report accessibility scan.

### Suggested Fix

Keep the semantic text label, but use the score panel's inverted background
and foreground tokens for badges placed inside that panel.

### Metadata

- Reproducible: yes
- Related Files: Frontend/src/features/dashboard/components/report-viewer.tsx, Frontend/e2e/dashboard.spec.ts

### Resolution

- **Resolved**: 2026-07-10T18:12:00Z
- **Notes**: Added a theme-safe inverted badge override and reran accessibility checks.

---

## [ERR-20260710-037] nextjs-security-scan-command-assumptions

**Logged**: 2026-07-10T18:20:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The first security-scan batch assumed the bundled dependency script was
executable and referenced the Next.js proxy from the wrong relative path.

### Error

```text
permission denied: .../scripts/dependency-audit.sh
rg: proxy.ts: No such file or directory
```

### Context

- Secret and pattern scanners completed; real environment files remained excluded.
- The actual proxy is `src/proxy.ts`.

### Suggested Fix

Invoke the read-only dependency scanner explicitly with `bash` and search the
live file map rather than assuming a root-level proxy path.

### Metadata

- Reproducible: yes
- Related Files: Frontend/src/proxy.ts, Frontend/package.json

### Resolution

- **Resolved**: 2026-07-10T18:20:00Z
- **Notes**: Reran the dependency audit through bash and corrected the manual scan paths.

---

## [ERR-20260710-038] security-audit-wrapper-required-jq

**Logged**: 2026-07-10T18:23:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The bundled dependency-audit wrapper could not parse npm's JSON because `jq`
is not installed, leaving blank counts and exiting with status 127.

### Error

```text
Vulnerability Summary: Critical: [blank] ... exit 127
```

### Context

- The wrapper did invoke `npm audit`, but its own parser was not portable to
  this workstation.
- No product dependency or source file caused the tool failure.

### Suggested Fix

Use the repository's `npm run security:audit` gate, which requires no external
JSON parser, and inspect `npm audit --json` directly only when details are needed.

### Metadata

- Reproducible: yes
- Related Files: Frontend/package.json

### Resolution

- **Resolved**: 2026-07-10T18:23:00Z
- **Notes**: Replaced the wrapper result with the native npm audit gate.

---

## [ERR-20260710-039] clerk-presence-awk-portability

**Logged**: 2026-07-10T18:31:00Z
**Priority**: low
**Status**: resolved
**Area**: developer tooling

### Summary

A secret-safe credential-presence check used an awk conditional expression
that the workstation awk rejected before reading any value.

### Error

```text
awk: syntax error at source line 1
```

### Context

- The command was intended to report only `present`, `absent`, or `undefined`.
- No environment value was printed.

### Suggested Fix

Use `grep -Eq '^VARIABLE=.+$'` for boolean presence checks instead of parsing
or printing the value.

### Metadata

- Reproducible: yes
- Related Files: .env.production

### Resolution

- **Resolved**: 2026-07-10T18:31:00Z
- **Notes**: Replaced the awk expression with a value-redacting grep presence check.

---

## [ERR-20260710-040] axe-standalone-required-browser-context

**Logged**: 2026-07-10T18:48:00Z
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary

The standalone public-page Axe smoke created a page directly from the browser,
but the installed Axe Playwright adapter requires an explicit browser context.

### Error

```text
Error: Please use browser.newContext()
```

### Context

- The public page and assets loaded before Axe rejected the test harness shape.
- The repository Playwright suite already uses fixture-provided contexts and was unaffected.

### Suggested Fix

Create `browser.newContext()` with the target viewport, then create the page
from that context before constructing `AxeBuilder`.

### Metadata

- Reproducible: yes
- Related Files: Frontend/e2e/dashboard.spec.ts

### Resolution

- **Resolved**: 2026-07-10T18:48:00Z
- **Notes**: Reran the public WCAG smoke with explicit isolated browser contexts.

---
