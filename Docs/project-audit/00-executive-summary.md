# ResumePilot audit: executive summary

Audit date: 2026-07-10
Mode: comprehensive audit, then small safe improvements
Baseline commit: `1740cb2`

## Verdict

ResumePilot is an evidence-first job-application workspace for job seekers who
want to compare a resume with a reviewed job description, generate a validated
application packet, approve any live-AI draft before it becomes product state,
export accepted content, and track the application. Its strongest product idea
is the claim-to-source boundary: unsupported resume claims are blocked instead
of being polished into plausible fiction.

The repository is a credible production-oriented MVP and a strong private-beta
baseline. It is not ready for a public multi-tenant launch and is not ready to
charge users. The deterministic workflow, durable operation queue, tenant
scoping, LangGraph approval checkpointing, validation gates, migration gate,
and broad automated tests are materially stronger than a typical prototype.
The remaining risks are concentrated in privacy operations, abuse controls,
deployment/restore capability, worker observability, and billing lifecycle
enforcement.

No confirmed P0 vulnerability was found, and no data loss was observed during
the audit. Several P1 defects can still produce missing files/checkpoints after
a failed cross-store deletion, excess usage under unresolved races, or retained
sensitive data. Versioned evidence-fit scoring and the audited partial analysis
finalization defect are now closed. The next engineering move is to expand
PostgreSQL workflow race coverage before broadening traffic or billing.

## Product and users

Primary users inferred from the product specification and interface are
students, early-career candidates, and active job seekers preparing repeated,
role-specific applications. The main journey is:

1. authenticate and upload a resume;
2. paste or fetch a job description, then review extracted evidence;
3. run deterministic matching and report validation;
4. optionally invoke consented live drafting through LangGraph;
5. approve or reject the paused proposal;
6. review evidence-linked resume bullets and export accepted content;
7. move the application through its preparation pipeline.

The current product is strongest from report generation through guarded export.
It is weakest before scoring, where parsed resume facts cannot be corrected,
and after application, where tracking stops at `applied`.

## Production scorecard

| Area | Status | Evidence and reason |
|---|---|---|
| Correctness | AMBER | Validation, versioned evidence-fit scoring, idempotent jobs, atomic replay-repairing finalization, and lease fencing are strong; full workflow races and cross-store privacy deletion still need hardening. |
| Security | AMBER | Signed internal identity, tenant-scoped repositories, upload bounds, SSRF controls, and non-root images are present. Public ingress rate/body limits, CSP, least-privilege database roles, and cloud controls are absent. |
| Architecture | AMBER | The modular monolith is the correct shape. Commit ownership is spread across large orchestration services and committing repositories, making partial-state defects difficult to prevent. |
| Database | AMBER | Alembic and the PostgreSQL migration gate now cover concurrent finalization in addition to migrations, locks, and checkpoints. Full workflows are still primarily tested on SQLite; timestamp columns are timezone-naive and cross-resource deletion is not atomic. |
| Performance | AMBER | Queue leasing and `SKIP LOCKED` support horizontal workers, but the shipped Compose topology has one serial worker and no measured load/queue budget. |
| Testing | GREEN | 220 backend tests at 88.90% measured application coverage, 13 Chromium E2E tests, 20 golden pairs, 38 labeled score cases with 14 monotonic pairwise expectations, build/lint/type checks, migration checks, dependency gates, and PostgreSQL finalization/score-migration checks passed. Broader load and full-workflow PostgreSQL races remain gaps. |
| UI/UX | AMBER | The evidence editor and guarded export are differentiated. The main workspace mixes user outcomes with developer diagnostics, repeats navigation, and overuses equal card surfaces. |
| Accessibility | AMBER | Initial axe coverage and semantic controls pass, but dynamic steps lack consistent focus movement/`aria-current`, and complex approval/report/mobile states are not scanned. |
| Deployment | RED | `docker-compose.yml` is explicitly a local production-like baseline. There is no selected public target, TLS ingress, staging promotion, IaC, or automated rollback. |
| Observability | RED | Health/readiness exist, but worker health, queue age, metrics, alerts, traces, and structured logs are absent; the formatter drops supplied `extra` fields. |
| Operations | RED | No executable backup/restore automation, restore drill, SLOs, incident process, or automated retention scheduler exists. |
| Monetization | RED | Limits and usage records exist, but checkout, portal, webhook ledger, subscription reconciliation, analytics, and support tooling do not. |

`GREEN` means the audited baseline is credible, not that the area is permanently
complete. `RED` marks a launch capability that is absent rather than a claim
that the current loopback demo is unsafe for its stated scope.

## Strongest qualities

- Evidence-linked reports and accepted-only export protect the product promise.
- Live AI is opt-in, paused for approval, revision-bound, and persisted through
  LangGraph checkpoints. LangChain is used only inside the LangGraph workflow;
  OpenClaw remains a separate private channel.
- Tenant-scoped reads, signed BFF identity, upload/archive limits, job URL SSRF
  defenses, audit sanitization, and privacy deletion tests show sound security
  instincts.
- Durable idempotent operations, leases, retry/dead-letter paths, migrations,
  dependency pins, container gates, and broad test coverage provide a solid
  engineering foundation.
- The project has a clear domain vocabulary: job evidence, resume evidence,
  claims, validation warnings, approval, application, draft, and export.

## Largest launch risks

1. **P1 — misleading match dimensions.** Candidate experience is not read when
   calculating the experience score, and responsibility matching accepts
   substrings such as `Go` inside `ongoing`.
2. **P1 — incomplete privacy lifecycle.** Retention is only run by a
   tenant-authenticated manual endpoint; browser users cannot delete/export
   account data; file/checkpoint deletion spans non-atomic stores.
3. **P1 — public abuse exposure.** No edge rate limit, bounded JSON-body helper,
   per-tenant storage quota, or job-preview concurrency budget exists.
4. **P1 — operational blindness.** A dead worker can leave the API ready while
   analyses stall. Backups and restore are instructions, not a tested system.
5. **P1 — public deployment absent.** TLS, secret management, role separation,
   network egress policy, staging, and rollback require a hosting decision.

## Safe improvements selected in this audit

The implementation batch deliberately avoids payment-provider, legal, cloud,
data-migration, and score-semantic decisions:

- paid plan privileges now fail closed to the free entitlement set unless the
  subscription status is explicitly `active`;
- old usage reservations still count while their backing workflow is active,
  closing the worker-outage quota bypass;
- successful analysis now presents the fit verdict before asking the user to
  tailor a resume, preserving approval recovery and leaving the editor one
  explicit action away;
- focused backend and browser regressions cover these paths;
- analysis finalization now commits report/application/audits/usage atomically,
  repairs completed replays, preserves superseding application work, and fences
  stale worker writes; SQLite crash injection and PostgreSQL concurrency gates
  cover the repaired contract.

## Coverage and exclusions

The audit covered all first-party frontend files, FastAPI routes, repositories,
schemas, migrations, core services, worker and LangGraph boundaries, OpenClaw
integration, configuration, Compose, CI, documentation, and test inventory.
Generated/vendor directories (`node_modules`, `.venv`, `.next`, caches), local
runtime data, credentials, binary artifacts, and the duplicated bundled product
document were excluded. The individual source documents were reviewed instead.

No real Clerk production login, Vertex call, public DNS-rebinding exercise,
load test, destructive migration, production database, cloud control, payment
flow, screen-reader session, or disaster restore was run. Customer demand,
willingness to pay, and pricing are hypotheses, not repository facts.

## Decision log

- Keep the modular monolith; do not introduce microservices or Kubernetes.
- Keep OpenClaw private and separate. Do not remove it.
- Use LangGraph only for the durable async approval workflow. Keep LangChain
  model construction inside LangGraph execution nodes.
- Treat deterministic evidence validation as a free safety boundary, not an
  upsell.
- Do not add billing until entitlement states, downgrade behavior, webhook
  ordering, and customer pricing have founder validation.
- Do not claim public-production readiness until deployment, recovery,
  observability, privacy, and abuse-control blockers are verified.

The detailed evidence and roadmap are in the other files in this directory.
