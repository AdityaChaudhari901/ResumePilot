# ResumePilot Deployment Runbook

This runbook covers the production-like Docker Compose stack for the current MVP.
It is intended for a private deployment or staging environment before adding
Stripe and public-user hardening.

## Runtime Shape

- `frontend`: Next.js dashboard and backend-for-frontend identity proxy.
- `backend`: FastAPI API, report generation, exports, readiness checks, and migrations.
- `db`: PostgreSQL.
- `OpenClaw`: stays outside Compose as a local/private gateway. Do not deploy one shared OpenClaw gateway for mutually untrusted users.

## Required Secrets

Create a production env file:

```bash
cp .env.production.example .env.production
```

Replace every `change-me-*` value with a long random value:

```bash
python - <<'PY'
import secrets
for name in ["POSTGRES_PASSWORD", "AUTH_TRUSTED_PROXY_SECRET", "JOBCOPILOT_API_TOKEN"]:
    print(f"{name}={secrets.token_urlsafe(48)}")
PY
```

For a private single-user stack, `RESUMEPILOT_AUTH_PROVIDER=local` is acceptable.
Before opening the app to real users, switch to `clerk` or `trusted_headers` and
keep `AUTH_REQUIRED=true` on the backend.

## Start

```bash
docker compose --env-file .env.production up --build
```

The backend service runs:

```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

Production startup fails if:

- `DATABASE_URL` uses SQLite.
- `AUTH_REQUIRED` is not true.
- `AUTH_TRUSTED_PROXY_SECRET` is missing.
- `JOBCOPILOT_API_TOKEN` is missing.
- schema auto-creation is enabled.
- migration readiness checks are disabled.

## Health Checks

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
curl -fsS http://127.0.0.1:3000/
```

`/health` proves the FastAPI process is alive. `/ready` proves the database is
reachable and, in production, that the database revision matches Alembic head.

## Migrations

Compose applies migrations before starting the API. For a manual migration:

```bash
docker compose --env-file .env.production run --rm backend alembic upgrade head
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
