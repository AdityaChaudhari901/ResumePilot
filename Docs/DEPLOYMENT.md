# ResumePilot Deployment Runbook

This runbook covers the production Docker Compose baseline. Put an HTTPS reverse
proxy in front of Next.js and keep the FastAPI port private to the host/network.

## Runtime Shape

- `frontend`: Next.js dashboard and backend-for-frontend identity proxy.
- `migrate`: one-shot Alembic and LangGraph checkpoint setup that must succeed before API/worker startup.
- `backend`: FastAPI command/query API and readiness checks.
- `worker`: PostgreSQL-leased analysis and PDF execution with retries,
  cancellation, dead-letter state, and a shared artifact volume.
- `db`: PostgreSQL.
- `OpenClaw`: stays outside Compose as a local/private gateway. Do not deploy one shared OpenClaw gateway for mutually untrusted users.

## Required Secrets

Create a production env file:

```bash
cp .env.production.example .env.production
```

Replace every `change-me-*` value with a long random value:

```bash
python3 - <<'PY'
import secrets
for name in ["POSTGRES_PASSWORD", "AUTH_TRUSTED_PROXY_SECRET", "JOBCOPILOT_API_TOKEN"]:
    print(f"{name}={secrets.token_urlsafe(48)}")
PY
```

Keep the same `POSTGRES_PASSWORD` for the lifetime of a persistent Compose
volume. The official PostgreSQL image applies `POSTGRES_PASSWORD` only when the
database volume is initialized; changing the env file later without rotating the
database user password will make the backend fail authentication.

The example fails closed with `RESUMEPILOT_AUTH_PROVIDER=clerk` and loopback-only
host bindings. Supply Clerk keys or switch to signed trusted headers before
starting it.

For a private single-user stack, `RESUMEPILOT_AUTH_PROVIDER=local` is acceptable.
Because Next.js runs with `NODE_ENV=production` in Compose, private local mode
also requires `RESUMEPILOT_ALLOW_LOCAL_AUTH_IN_PRODUCTION=true` and
`AUTH_TRUSTED_PROXY_SECRET`. Keep both bind hosts on `127.0.0.1`.

Before opening the app to real users, switch to `RESUMEPILOT_AUTH_PROVIDER=clerk`
or `trusted_headers`, set `RESUMEPILOT_ALLOW_LOCAL_AUTH_IN_PRODUCTION=false`, and
keep `AUTH_REQUIRED=true` on the backend. Clerk mode requires
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, and the shared
`AUTH_TRUSTED_PROXY_SECRET` so the Next.js BFF can sign tenant identity headers
for FastAPI.

Trusted-header mode also requires `RESUMEPILOT_TRUSTED_HEADER_SECRET` in the
Next.js runtime. The upstream proxy must sign the user, email, name, and
timestamp headers with HMAC-SHA256 and strip inbound copies before forwarding.
`RESUMEPILOT_TRUSTED_HEADER_TTL_SECONDS` accepts 30 to 3600 seconds and defaults
to 300.

## Release Boundaries

- The backend image uses hash-locked LangGraph, LangChain, Google GenAI, and
  PostgreSQL checkpointer dependencies. CrewAI and ChromaDB are absent.
- Live AI requires a premium plan plus explicit consent for each analysis. The
  provider payload excludes candidate contact fields, links, name occurrences,
  and the deterministic cover letter.
- LangGraph execution is durable but provider calls are at-least-once across a
  hard process crash. A call can repeat if Vertex returns immediately before the
  node checkpoint is committed. Monitor recorded usage against provider billing;
  checkpointed nodes and approval resumes do not rerun completed generation.
- Normal completion, cancellation, report deletion, and account deletion remove
  checkpoints directly. The worker also reconciles orphan and terminal threads
  at startup and every `WORKFLOW_CHECKPOINT_RECONCILE_SECONDS` (60 seconds by
  default), which bounds cleanup after an abrupt worker or account-deletion race.
- LangSmith tracing stays off by default so resume and draft content cannot
  leave the application through an observability integration. Production Vertex
  access should use Workload Identity or an attached least-privilege service account.
- The amd64 image installs checksum-pinned Tectonic. Arm64 deployments must
  provide a verified compiler or leave PDF export unavailable. PDF compilation
  runs in the worker; apply network and resource isolation before sustained load.
- The API and worker currently share generated artifacts through the Compose
  data volume. Use encrypted object storage before scaling them across hosts.
- Put request-rate and body-size controls at the HTTPS reverse proxy. Keep
  private/link-local/metadata egress blocked even though the application also
  validates job URL DNS, redirects, and connected peers.
- OpenClaw Control redirects work only with private local auth and a loopback
  gateway. Do not share one gateway token across public tenants.

## Start

```bash
docker compose --env-file .env.production --progress=plain up --build
```

The example env binds host ports `8050` and `3050` to `127.0.0.1`. A host-level
HTTPS reverse proxy may forward public traffic to Next.js on `3050`; do not
forward the FastAPI port publicly.

The migration, API, and worker services run:

```bash
python scripts/migrate_runtime.py
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
resumepilot-worker
```

Production startup fails if:

- `DATABASE_URL` uses SQLite.
- `AUTH_REQUIRED` is not true.
- `AUTH_TRUSTED_PROXY_SECRET` is missing.
- `JOBCOPILOT_API_TOKEN` is missing.
- schema auto-creation is enabled.
- migration readiness checks are disabled.

Keep checkpoint reconciliation enabled in every worker deployment:

```env
WORKFLOW_CHECKPOINT_RECONCILE_SECONDS=60
```

The accepted range is 10 to 3600 seconds. Lower values shorten the residual
cleanup window at the cost of more PostgreSQL maintenance queries.

## Health Checks

```bash
curl -fsS http://127.0.0.1:8050/health
curl -fsS http://127.0.0.1:8050/ready
curl -fsS http://127.0.0.1:3050/
```

`/health` proves the FastAPI process is alive. `/ready` proves the database is
reachable, the Alembic revision matches, and LangGraph checkpoint tables exist.

## Migrations

Compose applies migrations before starting the API. For a manual migration:

```bash
docker compose --env-file .env.production run --rm migrate
```

Do not rely on SQLAlchemy `create_all` in production. The backend disables
automatic schema creation by default when `APP_ENV=production`.

## Rollback

Before running migrations against persistent data:

1. Take a PostgreSQL backup.
2. Record the current image tag or commit SHA.
3. Run migrations.
4. Confirm `/ready` returns `status: ok`.

If deployment fails before data changes, roll back the image. If a migration has
already run, restore from backup or apply a reviewed Alembic downgrade only after
checking data-loss risk.
