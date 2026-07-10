# UI, UX, accessibility, and product audit

## Product experience verdict

ResumePilot's differentiated experience is not “AI writes a resume.” It is an
application dossier in which every recommendation can be traced to resume and
job evidence, unsafe claims are blocked, and live suggestions require approval.
The bullet comparison and accepted-only export express that promise well.

The current dashboard also behaves like a developer console: operational
health, FastAPI, provider setup, OpenClaw commands, internal model cost, and
workflow trace compete with the job seeker's next action. Two progress summaries
and repeated rounded cards produce a 4,959 px desktop capture and an 8,226 px
mobile capture in the audited E2E fixture. Those measurements describe the
fixture, not a universal user session, but they confirm the hierarchy problem.

## Journey audit

| Stage | Current strength | Friction | Recommended outcome |
|---|---|---|---|
| Sign in | Clerk/local/trusted-header modes are explicit | No short privacy/value onboarding | Explain stored data, evidence review, and first value before upload |
| Job capture | URL plus strong paste fallback | Job-first order conflicts with “upload once, reuse” | Allow either start, then establish a reusable default resume |
| Job review | Users can edit role, company, skills, and responsibilities | Blank manually added skill evidence receives a synthetic placeholder | Require a source quote or mark provenance as `manual_confirmed` |
| Resume upload | Type/signature parsing is robust | Parsed facts are read-only and hidden in diagnostics | Confirm/correct low-confidence facts before scoring |
| Analysis | Durable, consented, recoverable approval path | UI describes orchestration more than outcome | Call the action “Build application kit”; keep internals secondary |
| Result | Detailed evidence report exists | Previously opened the editor before the fit decision | **Fixed:** show the validated fit report first, then explicit tailoring CTA |
| Draft review | Original/proposed comparison and evidence labels | Unsaved local edits can disappear | Debounced revision-safe autosave or Save/Discard navigation guard |
| Export | PDF, DOCX, LaTeX, Markdown with validation boundary | Four formats have equal visual weight | PDF/DOCX primary; technical formats under “More” |
| Tracking | Preparation stages are visible | Stops at `applied`; no dates, notes, interviews, offers, or outcomes | Extend lifecycle after submission and capture next action |
| Privacy | Backend deletion exists | Browser user cannot delete/export account data | Privacy center with re-authentication, receipts, and tombstone semantics |

## Prioritized product and UX findings

### PROD-01 — P1 — Resume evidence cannot be confirmed before scoring

- **Evidence:** `dashboard-shell.tsx:493-503,1465-1494` and
  `resume-profile-review-card.tsx:81-128` show upload advancing to analysis while
  the parsed profile remains read-only.
- **Impact:** a parser error becomes the basis of the score and generated packet.
- **Smallest valuable version:** persist a versioned correction layer for
  low-confidence employer, role, education, skills, and fact fields. Require an
  explicit confirmation before the first analysis.
- **Measure:** correction rate, percent of analyses with confirmed evidence, and
  support reports about incorrect extraction.

### UX-01 — P1, fixed in this batch — The fit decision was skipped

- **Evidence:** successful analysis paths in `dashboard-shell.tsx` previously
  selected `draft` immediately.
- **Change:** new, resumed, and approved analyses select `report`. The report
  header exposes a primary `Review tailored resume` action, leaving the editor
  one explicit step away.
- **Impact:** users can decide whether a role is worth tailoring before doing
  editing work.
- **Validation:** desktop and mobile Playwright paths assert the report appears,
  the editor is absent until the CTA is activated, and unsupported-edit
  validation still behaves as before.

### PROD-02 — P1 — Manually added job skills can look source-backed

- **Evidence:** `job-evidence-review-card.tsx:401-410` substitutes a generic
  “skill added during review” sentence when evidence is blank.
- **Impact:** user-entered requirements can inflate a score while appearing
  quoted from the job description.
- **Remedy:** blank evidence blocks source-backed save; alternatively persist a
  visibly distinct `manual_confirmed` provenance that is never rendered as a
  source quote.

### PROD-03 — P1 — Resume reuse is promised but not surfaced

The product specification says upload once and reuse, while a restored/fresh
dashboard has no resume library/default selector. Add one default resume with a
version label, last-used time, duplicate-hash reuse, replace, and delete actions.
Measure second-application completion without re-upload.

### PROD-04 — P1 — Privacy operations are inaccessible

Backend report/resume/account deletion routes exist, but browser BFF/UI paths do
not. Add a privacy center only after defining identity-provider deletion and
recreation semantics. This is a launch control, not a premium feature.

### A11Y-01 — P1 — Dynamic step changes can lose focus

`dashboard-shell.tsx:1337-1416` replaces step content, while
`workflow-progress.tsx:20-66` does not identify the current step with
`aria-current="step"`. Approval is the only path that explicitly moves focus.
Give each intentional destination a focusable heading, set current-step
semantics, and do not move focus during background polling.

### UX-02 — P2 — Customer and developer views are mixed

Move OpenClaw setup, raw shell commands, backend URLs, model registry, provider
credentials, and internal provider cost into a collapsed local/developer
integration area. Keep OpenClaw itself. A customer view can state “Private AI
connection: available/unavailable” without exposing diagnostics.

### UX-03 — P2 — Navigation and card hierarchy are redundant

The full progress strip and workflow summary represent the same six stages.
`Panel` also gives nearly every section the same border/radius/shadow, so
decisions and reference material have equal weight. Use one adaptive application
rail, quiet dossier sections, and raised surfaces only for decisions or overlays.

### UX-04 — P2 — Tailored edits can be lost

`tailored-resume-workspace-card.tsx:222-244` keeps text locally until an explicit
save/accept/reject. First add a Save/Discard navigation guard; then consider
debounced autosave with revision conflict handling. Test refresh, application
switch, stale revision, and network failure.

### PROD-05 — P2 — Application tracking stops where retention begins

Current states end at `applied`. Add `interviewing`, `offer`, `rejected`, and
`withdrawn`, plus stage timestamps, one note, and a next-action date. Derive
`exported` from a real export rather than accepting a manual state assertion.

### PROD-06 — P2 — One percentage appears more precise than its model

The report shows a match percentage and counts, but not required/preferred
coverage, evidence strength, or extraction confidence. Label it as a
resume-to-JD evidence heuristic—not hiring probability—and show a breakdown
that reconciles exactly with deterministic inputs.

## Visual direction: the evidence desk

The interface should feel like a calm editorial evidence desk for an anxious
job seeker, not a generic AI dashboard.

### Domain vocabulary

Use application dossier, job brief, evidence ledger, proof margin, revision,
validation stamp, submission packet, and career pipeline. Avoid robots,
sparkles, magic language, and abstract “AI power.”

### Signature interaction: Evidence Rail

Selecting a score component, bullet, cover-letter sentence, or interview point
opens the exact resume and job excerpts beside it with a visible claim-to-source
connection. The same interaction should work across verdict, tailoring, cover
letter, and interview prep. This is a reusable product behavior, not decoration.

### Visual system

- **Color:** resume-paper ivory, graphite, annotation blue, validation green,
  highlighter amber, proofreader red, and filing-rule gray. One accent per state.
- **Type:** self-hosted Source Sans 3 for interface text, Source Serif 4 for
  report/document preview, mono only for identifiers and measurements.
- **Spacing:** 4 px base; 12–16 px inside controls, 24 px between sections,
  32 px between major stages.
- **Depth:** tonal shifts and quiet rules. Remove the universal `shadow-sm`;
  reserve elevation for dialogs, decisions, and temporary overlays.
- **Radius:** 6 px controls, 8 px panels, larger only for overlays.
- **Desktop:** one application rail, one focused dossier, contextual evidence
  inspector rather than a permanent wall of cards.
- **Mobile:** compact current-step header, one task at a time, sticky primary
  action, and application history in a drawer.
- **Motion:** 120–180 ms functional transitions with a global reduced-motion
  fallback. Never animate polling changes solely for novelty.
- **Visualization:** required/preferred/evidence coverage bars; no decorative
  charts or hiring-probability gauge.

### Replace these patterns

- six equal progress cards → one compact numbered rail;
- repeated rounded cards → editorial sections and annotation margins;
- provider names in the primary journey → user outcome and consent language;
- always-visible technical trace → collapsed validation details;
- four equal exports → PDF/DOCX primary and technical formats secondary;
- empty placeholder cards → one useful next action plus a concise example.

## Accessibility program

1. Add `aria-current="step"` and intentional focus management across all six
   steps, including failure and approval recovery.
2. Run axe after job evidence editing, waiting approval, report, blocked edit,
   tailored draft, privacy confirmation, and mobile states—not only initial load.
3. Add keyboard-order, 200% zoom/reflow, reduced-motion, and error-summary tests.
4. Preserve visible focus, descriptive labels, live-region restraint, and
   non-color status cues in the new design system.
5. Run a real VoiceOver or NVDA journey before public launch; automated checks
   are not a screen-reader usability claim.

## Feature priorities

| Timing | Action | Smallest valuable version | Success signal |
|---|---|---|---|
| Now | Improve fit decision | Report before tailoring, implemented | Report viewed before draft editing |
| Now | Confirm resume evidence | Correct low-confidence parsed facts | Corrections persist and drive later output |
| Now | Add resume reuse | One saved default resume | Second application without re-upload |
| Now | Protect draft edits | Save/Discard guard | No silent edit loss in tested navigation paths |
| Now | Add privacy center | Delete/export controls with safe identity semantics | Self-service completion without support |
| Near term | Explain score | Required/preferred/evidence breakdown | Evidence detail engagement and fewer score-confusion reports |
| Near term | Extend pipeline | Four post-apply states, timestamps, note, next action | Users update applications after submission |
| Near term | Export history | Format, revision, filename, hash, time | Safe re-download and provenance |
| Later | Outcome feedback | Optional interview/offer outcome and reason | Useful voluntary outcome completion |
| Defer | Coach/team mode | Wait for individual activation and organization-isolation evidence | Repeated validated demand from coaches/placement cells |

## Product analytics boundary

There is no product analytics implementation. Add a provider-neutral event
interface only after a privacy schema is approved. Allow internal IDs, plan,
categorical state, format, duration, and error class. Prohibit resume text, job
text, names, email, phone, source excerpts, and generated prose.

Minimum funnel events are `resume_confirmed`, `job_evidence_saved`,
`validated_report_completed`, `tailored_bullet_accepted|rejected`,
`export_completed`, `application_stage_changed`, `upgrade_prompt_viewed`, and
optional `interview_outcome_reported`. Measure activation as a validated report
viewed and at least one evidence-backed next action—not mere signup.
