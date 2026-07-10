# Monetization and billing-readiness recommendation

## Verdict

ResumePilot should use freemium acquisition plus one paid individual plan while
the core journey and willingness to pay are validated. Its paid value is not
unlimited prose generation; it is repeated, trustworthy application preparation
with evidence review, resume reuse, live-draft convenience, export history, and
post-application organization.

The product is not ready to charge. Usage events, reservation semantics, plan
fields, and hard limits are a useful foundation, but there is no checkout,
billing portal, subscription table, webhook ledger, lifecycle reconciliation,
payment recovery, product analytics, or support view. This audit does not add a
payment provider or price IDs because those would encode unvalidated business
and infrastructure decisions.

## Verified current state

`Backend/app/services/usage_service.py` defines:

| Stored plan | Monthly analyses | Monthly exports | Live AI runs | Live AI enabled |
|---|---:|---:|---:|---|
| Free | 3 | 5 | 0 | No |
| Pro | 100 | 100 | 0 | No |
| Premium | 500 | 500 | 100 | Yes |

These are source-code constants, not products linked to billing. `users` stores
`plan`, `subscription_status`, and an optional `stripe_customer_id`; the UI
explicitly says Stripe is not connected. The audit batch now treats paid plan
definitions as effective only when `subscription_status == "active"`. That is a
safe fail-closed control, not a complete subscription lifecycle.

## Market context

Public competitor prices were checked on 2026-07-10 only to bound a hypothesis:

- [Rezi pricing](https://www.rezi.ai/pricing) advertised a US$29 monthly plan
  and a US$149 lifetime option.
- [Teal pricing](https://www.tealhq.com/pricing) advertised US$13 weekly,
  US$29 monthly, and US$79 quarterly options.
- [Huntr pricing](https://api.huntr.co/pricing) advertised a US$40 monthly plan
  with longer-term discounts.

Feature bundles, regions, promotions, taxes, and prices can change. These pages
do not prove ResumePilot demand or justify copying a price. The likely core
audience includes cost-sensitive students and job seekers in India, so direct
purchase-intent testing matters more than nominal competitor anchors.

## Recommended packaging hypothesis

Start with two visible individual packages. Do not ship both a subscription and
a sprint pass until testing identifies which mental model users prefer.

| Package | Target | Hypothesized entitlement | Upgrade moment |
|---|---|---|---|
| Free | New or occasional job seeker | 3 evidence analyses/month, 5 exports, deterministic workflow, one default resume, basic application pipeline, full validation/privacy controls | Fourth analysis, another resume version, live drafting, export history |
| Job Search Pro | Active searcher | 40–50 analyses, 40–50 exports, 20 live-draft runs, resume versions, export history, full tracker/reminders | Repeated weekly applications and workflow convenience |

Price test, not committed price:

- US$12–15/month and ₹799–999/month for Job Search Pro; or
- a US$19–29 / locally adjusted 30-day “Job Search Sprint” pass for an episodic
  search.

The current 500-analysis premium allowance is too high to treat as a launch
default without real provider-cost and abuse data. Retain source compatibility
until the billing catalog exists, then migrate entitlements explicitly.

Do not launch a coach/placement plan yet. A later US$39–59 per-seat hypothesis
requires organization isolation, client consent, role-based access, data
processing terms, and repeated customer demand.

## What should never be paywalled

- evidence confirmation and source visibility;
- unsupported-claim blocking and validation warnings;
- account export/deletion and other privacy controls;
- the first complete fit verdict;
- at least one practical PDF or DOCX export;
- safe deterministic fallback when live AI is unavailable.

Paywall workflow volume and convenience, not truthfulness or user control.

## Upgrade triggers

Use contextual triggers that follow proven intent:

- before the fourth monthly analysis, show remaining allowance and the value of
  reuse/history—never surprise the user after work is submitted;
- when a user asks for live drafting, explain what data is sent, the approval
  pause, and the included live-run allowance;
- when adding another resume version or setting a reminder, explain the paid
  workflow benefit;
- after a successful free export, offer continued tracking/history without
  blocking the completed artifact.

Avoid generic upgrade banners on every screen. Record prompt view, checkout
start, success/failure, and later retention with no sensitive content.

## Entitlement architecture

Create one server-owned effective-entitlement boundary used by API, worker,
BFF display, and support tools:

```text
billing provider events
        |
        v
verified idempotent event ledger
        |
        v
normalized subscription record + catalog product
        |
        v
effective_entitlements(user, now)
        |
        +-> usage reservation and execution gates
        +-> usage summary / upgrade UI
        +-> support reconciliation
```

The result should include plan key, source, effective status, period bounds,
grace deadline, limits, live-AI permission, and reason code. The worker must
recheck entitlement immediately before a billable provider call while honoring
an already-approved, documented grace rule.

Founder decisions required before implementation:

- which provider and merchant entity/currency/tax setup;
- allowed lifecycle states (`trialing`, `active`, `past_due`, grace, `unpaid`,
  `canceled`, `incomplete`) and exact grace periods;
- immediate versus period-end downgrades;
- whether a queued/reserved operation may finish after downgrade;
- refunds, chargebacks, admin overrides, and lifetime/sprint-pass semantics;
- regional pricing and whether taxes are inclusive.

## Billing implementation requirements

1. Internal product/price catalog; provider price IDs stay inside the adapter.
2. Subscription table with provider/customer/subscription IDs, normalized
   status, period bounds, cancel settings, source-event time, and version.
3. Signature-verified webhook route and append-only event ledger with unique
   provider event ID, payload hash, processing status, and retry details.
4. Idempotent, out-of-order-safe reducer. An older event cannot overwrite a
   newer subscription state merely because it arrives later.
5. Hosted checkout-session endpoint and hosted billing-portal endpoint; do not
   collect raw payment details.
6. Effective-entitlement service plus audit reason codes and an admin/support
   reconciliation view.
7. Downgrades block new paid work without deleting existing user artifacts.
8. Existing transactionally reserved usage remains behind entitlement checks;
   active workflow reservations remain quota-bearing.
9. Revision-bound idempotency for every billable export and model operation.
10. Tests for duplicate/out-of-order events, signature failure, failed payment,
    grace expiry, cancellation, plan change, refund/chargeback, concurrent quota,
    and support override expiry.

Stripe's own guidance emphasizes asynchronous subscription webhooks and a
hosted customer portal; if Stripe is selected, use those primitives rather than
polling or building card-management UI:

- [Stripe subscription webhooks](https://docs.stripe.com/billing/subscriptions/webhooks)
- [Stripe customer portal](https://docs.stripe.com/customer-management)
- [Stripe subscription overview](https://docs.stripe.com/billing/subscriptions/overview)

These links explain a possible adapter, not a provider decision.

## Cost and margin controls

- Store provider/model, operation ID, input/output usage, estimated cost,
  completion status, and pricing-version reference; never store prompt text in
  analytics.
- Set per-user live-run limits, global daily spend ceiling, provider timeout,
  and a deterministic fallback that preserves a useful result.
- Alert on cost per completed approved live run, reservation-to-completion ratio,
  repeated failures, and abnormal tenant usage.
- Reconcile estimated usage with provider invoices before setting final limits.
- Do not add overage billing at launch. Hard allowances and upgrades are easier
  to explain and support.

## Monetization measurement

Minimum privacy-conscious funnel:

1. `validated_report_completed`
2. `fit_report_viewed`
3. `tailoring_started`
4. `tailored_bullet_accepted|rejected`
5. `export_completed`
6. `application_stage_changed`
7. `upgrade_prompt_viewed`
8. `checkout_started|completed|failed`
9. `subscription_canceled`
10. optional `interview_outcome_reported`

Track conversion by plan, acquisition cohort, and categorical workflow state,
plus provider cost per completed paid outcome. Do not send names, contact data,
resume/job text, source excerpts, generated prose, or raw URLs. Add schema
allowlist and redaction tests before selecting an analytics vendor.

## Validation plan

Before building billing:

- interview at least two distinct segments about frequency, current workaround,
  trust concerns, preferred pass/subscription model, and price sensitivity;
- run a non-charging plan-comparison/purchase-intent test;
- measure free activation and repeated weekly use;
- estimate live-AI unit cost from real beta runs;
- define support, refund, tax, privacy, and legal ownership.

Success is not checkout completion alone. A viable paid plan should improve the
rate of validated reports that become accepted, exported, and actively tracked
applications while maintaining supportable gross margin and low refund pressure.
