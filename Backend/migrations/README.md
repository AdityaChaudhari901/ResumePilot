# Alembic Migrations

Migration files for the FastAPI backend.

Useful commands from `Backend/`:

```bash
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

Runtime table creation still exists for local MVP ergonomics, but production-like environments should apply migrations explicitly before starting the API.
