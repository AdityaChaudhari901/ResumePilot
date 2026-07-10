# Prioritized production and product roadmap

This roadmap keeps the modular monolith, OpenClaw, deterministic evidence
boundary, and LangGraph approval design. Priorities reflect verified risk and
user value, not feature volume. `S`, `M`, and `L` are relative engineering
effort, not calendar promises.

## Completed in the 2026-07-10 audit batch

### Fail-closed paid entitlements and active reservations

- **Outcome:** inactive paid rows cannot consume premium/live-AI privileges;
  queued/running/waiting work cannot age out of quota accounting.
- **Scope:** effective-plan selection, active workflow status definition,
  reservation query, backend regressions.
- **Dependencies:** none.
- **Effort:** S.
- **Risk:** Low; active premium and normal reservation behavior are preserved.
- **Definition of done:** inactive premium is reported/enforced as free, does
  not enter LangGraph, and an old active free-plan reservation blocks excess work.
- **Success measure:** regression suite passes and no execution path derives
  paid permission from plan name alone.

### Outcome-first analysis completion

- **Outcome:** users see the validated fit decision before spending time on
  tailoring.
- **Scope:** dashboard success/recovery transitions, report CTA, Playwright paths.
- **Dependencies:** existing report and tailored workspace.
- **Effort:** S.
- **Risk:** Low; no API or approval-state change.
- **Definition of done:** new, resumed, and approved analyses open the report;
  the editor remains one explicit action away on desktop and mobile.
- **Success measure:** E2E proves ordering; future analytics should measure
  report-view-before-tailoring rate.

## Immediate: before launch or next release

### 1. Make analysis finalization atomic and replay-repairing — P1

- **Outcome:** one operation always converges to one complete application result
  and one quota charge after any retry.
- **Scope:** `analysis_service.py`, `application_service.py`, audit persistence,
  usage settlement, workflow finalization, stable idempotency key.
- **Dependencies:** characterize current application/report semantics; decide
  audit-event uniqueness representation.
- **Effort:** M.
- **Risk:** Medium because commit ownership changes in a core workflow.
- **Definition of done:** fault injection after every persistence boundary
  converges to exactly one analysis, application link, audit correlation, usage
  settlement, and succeeded workflow; no early completed-analysis path skips repair.
- **Success measure:** zero incomplete-success fixtures across repeated SQLite and
  PostgreSQL runs; support query can prove correlation by operation ID.

### 2. Correct and version match-score semantics — P1

- **Outcome:** score components measure candidate evidence and never match token
  substrings accidentally.
- **Scope:** structured experience evidence or explicit unknown state,
  token-boundary responsibility matching, score version, report explanation,
  labeled evaluation corpus.
- **Dependencies:** product decision on neutral/unknown experience display and
  migration/display of historical score versions.
- **Effort:** M.
- **Risk:** Medium; users may see different scores for the same inputs.
- **Definition of done:** junior/senior counterexamples rank correctly, `Go`
  does not match `ongoing`, score breakdown reconciles to inputs, and historical
  reports keep their original version.
- **Success measure:** reviewed benchmark passes expected matches, forbidden
  matches, score bands/pairwise order, and evidence confidence.

### 3. Add PostgreSQL workflow integrity tests — P1

- **Outcome:** production-only locks, leases, and concurrency behavior are
  verified rather than inferred from SQLite.
- **Scope:** quota reservation race, approval-versus-cancel, finalization replay,
  privacy tombstone/checkpoint cleanup; repeat-race CI job.
- **Dependencies:** item 1 finalizer contract and disposable PostgreSQL in CI.
- **Effort:** M.
- **Risk:** Low application risk; moderate CI flake risk if synchronization is poor.
- **Definition of done:** deterministic barriers replace timing sleeps; each race
  asserts one terminal result, one charge, tenant isolation, and no orphan checkpoint.
- **Success measure:** repeated CI runs remain green and fail against known-bad
  transaction implementations.

### 4. Close public ingress and runtime privilege gaps — P1

- **Outcome:** one tenant cannot exhaust shared resources, and one compromised
  runtime does not automatically gain migration/all-tenant privilege.
- **Scope:** bounded BFF bodies, user/IP rate limits, storage/count quotas,
  preview concurrency, egress policy, separate DB roles/secrets, minimal health.
- **Dependencies:** hosting/edge selection and expected beta traffic/storage budgets.
- **Effort:** M–L.
- **Risk:** Medium; overly strict budgets can block legitimate use.
- **Definition of done:** chunked/large bodies return `413`, excess rates return
  `429`, tenant storage is bounded, runtime roles cannot DDL, and public health
  omits internal topology.
- **Success measure:** load/abuse test stays within memory/disk/outbound budgets;
  privilege tests and alerts pass.

### 5. Operationalize worker health, backup, and restore — P1

- **Outcome:** stalled work and data loss become detectable and recoverable.
- **Scope:** JSON logs, worker heartbeat, queue/dead-letter/provider metrics,
  alerts, managed backup/PITR or scripts, artifact policy, restore drill, runbooks.
- **Dependencies:** hosting target, telemetry system, founder-approved RPO/RTO,
  on-call ownership.
- **Effort:** M–L.
- **Risk:** Low to product behavior; medium operational integration risk.
- **Definition of done:** killing/hanging a worker degrades a visible signal and
  alerts; a clean environment restores database/artifacts, migrates, and passes
  tenant counts/hash/readiness checks.
- **Success measure:** measured detection time and restore time meet the approved
  objectives in a recorded drill.

### 6. Implement durable privacy lifecycle — P1

- **Outcome:** retention and user deletion complete safely across database,
  checkpoints, artifacts, and identity sessions.
- **Scope:** deletion request/tombstone, quarantine/idempotent cleanup,
  scheduled cursor-batched retention, receipts, lag metrics, BFF privacy center,
  account export, external-ID recreation block.
- **Dependencies:** founder/legal retention and identity-provider deletion policy.
- **Effort:** L.
- **Risk:** Medium-high because irreversible deletion crosses stores.
- **Definition of done:** failure injection at every store boundary converges;
  expired multi-tenant fixtures purge only eligible data; browser deletion signs
  out and cannot silently recreate the account.
- **Success measure:** zero eligible records beyond approved deletion lag and
  successful self-service completion without support intervention.

### 7. Define a public deployment and trust package — P1

- **Outcome:** reproducible, private-by-default public deployment with rollback
  and accurate customer disclosures.
- **Scope:** IaC, TLS/HSTS/CSP, private API/DB, secret manager, immutable images,
  migration job, staging/promotion/rollback, privacy policy, terms, AI/provider
  disclosure, security/support contact.
- **Dependencies:** cloud/provider, domain, budget, legal counsel, incident owner.
- **Effort:** L.
- **Risk:** Medium; provider-specific choices create operating commitments.
- **Definition of done:** a clean staging deployment passes TLS, network
  isolation, secret, migration, smoke, alert, rollback, and policy-link checks.
- **Success measure:** repeatable deploy/rollback evidence and no undocumented
  public data flow.

### 8. Decide OpenClaw public-launch scope — P1 if included

- **Outcome:** OpenClaw remains useful without bypassing tenant identity,
  durability, idempotency, or usage policy.
- **Scope:** dedicated service identity, sender-to-tenant mapping, mandatory
  allowlist/rate limits, durable operation API, idempotency, production auth test.
- **Dependencies:** founder decision whether OpenClaw is private integration or
  a supported customer channel.
- **Effort:** M.
- **Risk:** Medium; identity mapping is security-sensitive.
- **Definition of done:** replay produces one operation/charge, unknown senders
  are denied, tenants cannot cross, and no synchronous analysis bypass remains.
- **Success measure:** production-auth integration tests pass and the private
  channel has observable error/latency budgets.

## Near term: next 30 days

### 9. Confirm and reuse resume evidence

- **Outcome:** repeat users trust parsed facts and start later applications
  without re-uploading.
- **Scope:** versioned correction overlay, confidence flags, confirmation gate,
  one default resume, version label/last-used, replace/delete flows.
- **Dependencies:** correction schema and privacy lifecycle item 6.
- **Effort:** M–L.
- **Risk:** Medium; corrections must not fabricate source evidence.
- **Definition of done:** corrected facts persist, visibly retain provenance,
  drive later matching/export, and a second application can use the default.
- **Success measure:** confirmed-evidence rate, correction rate, second application
  without upload, and reduced extraction-related support reports.

### 10. Simplify the workspace and complete dynamic accessibility

- **Outcome:** one clear next action with reliable keyboard/screen-reader context.
- **Scope:** one application rail, developer diagnostics disclosure, evidence
  dossier hierarchy, primary/secondary exports, `aria-current`, destination
  focus, complex-state axe/keyboard/mobile/zoom/reduced-motion tests.
- **Dependencies:** no backend change; design-token and content review.
- **Effort:** M.
- **Risk:** Medium visual regression risk.
- **Definition of done:** duplicate progress UI is removed, diagnostics remain
  available but secondary, and all six intentional transitions pass keyboard and
  automated accessibility checks at mobile/desktop breakpoints.
- **Success measure:** reduced fixture scroll depth and task time, no serious axe
  violations, and successful manual screen-reader beta journey.

### 11. Protect drafts and extend post-application tracking

- **Outcome:** editing work is not lost and ResumePilot remains useful after export.
- **Scope:** Save/Discard guard then revision-safe autosave, export history,
  interview/offer/rejected/withdrawn states, timestamps, note, next-action date,
  export-derived status.
- **Dependencies:** agreed transition matrix and notification scope (initially
  in-app, not email/SMS).
- **Effort:** M.
- **Risk:** Medium due conflict and state-migration semantics.
- **Definition of done:** refresh/navigation cannot silently lose edits; stage
  transitions are valid/audited; an export can be re-downloaded by revision.
- **Success measure:** draft recovery, post-`applied` update rate, applications
  with a next action, and safe re-download completion.

### 12. Add privacy-safe product analytics and pricing research

- **Outcome:** activation, retention, outcome, and upgrade decisions use evidence.
- **Scope:** provider-neutral allowlisted event schema, redaction tests, funnel
  queries, purchase-intent experiment, interviews, provider-cost reconciliation.
- **Dependencies:** privacy/legal approval and analytics hosting decision.
- **Effort:** M.
- **Risk:** Low technical risk; high trust risk if sensitive content leaks.
- **Definition of done:** events contain no resume/JD/contact/generated content;
  activation and upgrade funnels run on synthetic and beta data; research notes
  distinguish segments and hypotheses.
- **Success measure:** validated activation baseline, repeated-use cohort,
  purchase intent, and cost per completed paid live outcome.

### 13. Build billing only after entitlement and price decisions

- **Outcome:** charge and revoke access consistently without deleting user work.
- **Scope:** product catalog, subscription and event-ledger tables, signed
  idempotent webhooks, out-of-order reducer, hosted checkout/portal, support
  reconciliation, effective entitlements, failed-payment/grace/downgrade tests.
- **Dependencies:** item 12 evidence; provider, tax/currency, lifecycle, refund,
  and grace decisions.
- **Effort:** L.
- **Risk:** Medium-high financial and support risk.
- **Definition of done:** duplicate/out-of-order events converge, inactive/unpaid
  users cannot start paid work, downgrades preserve artifacts, and support can
  explain every entitlement with an audit reason.
- **Success measure:** checkout completion, payment recovery, low entitlement
  dispute rate, refund rate, retained paid users, and sustainable gross margin.

## Medium term: 31–90 days

### 14. Scale from measured queue and storage demand

- **Outcome:** beta growth does not create head-of-line blocking or unbounded
  privacy/storage cost.
- **Scope:** queue/load benchmark, safe worker replicas, optional export capacity
  isolation, object storage with encryption/lifecycle, batched privacy queries,
  keyset pagination, timestamp migration.
- **Dependencies:** observability item 5, hosting item 7, measured bottlenecks,
  backup/lifecycle design.
- **Effort:** L.
- **Risk:** Medium; infrastructure and data migrations.
- **Definition of done:** capacity test meets queue/latency budgets; object and DB
  lifecycle/restore/deletion checks pass; history has stable cursor pagination;
  timestamps serialize RFC 3339 UTC.
- **Success measure:** p95 queue start/API latency within approved targets,
  bounded memory/query counts, and known storage cost per active user.

### 15. Close the outcome-learning loop

- **Outcome:** recommendations improve using voluntary job-search outcomes rather
  than opaque model confidence.
- **Scope:** optional interview/offer/rejection outcome, reason categories,
  cohort analysis, reviewed score-quality benchmark expansion.
- **Dependencies:** analytics/privacy boundary and sufficient consenting users.
- **Effort:** M.
- **Risk:** Medium privacy and causal-interpretation risk.
- **Definition of done:** outcomes are optional, deletable, content-minimal, and
  never presented as proof of causation; benchmark changes undergo review.
- **Success measure:** useful completion rate, segment-level calibration insight,
  and fewer verified false-positive/false-negative score cases.

### 16. Evaluate coach/placement workflows only on demand

- **Outcome:** avoid premature multi-tenant organization complexity while
  preserving a credible expansion path.
- **Scope:** discovery only first; if validated, organization/client isolation,
  roles, consent, audit/export, and data-processing controls.
- **Dependencies:** strong individual activation/retention and repeated paid
  demand from coaches or placement teams.
- **Effort:** L after discovery.
- **Risk:** High security/privacy complexity.
- **Definition of done:** no implementation until discovery has a named buyer,
  recurring workflow, acceptable data model, and purchase intent.
- **Success measure:** qualified design partners and paid pilot intent—not feature
  requests alone.

## Explicitly deferred

- microservices, Kubernetes, event streaming, and a separate queue product;
- automatic resume rewrites without evidence approval;
- usage overages at launch;
- broad collaboration/team mode;
- public Chromium job scraping without network isolation;
- payment UI before lifecycle and entitlement decisions;
- decorative AI redesigns that weaken evidence visibility.
