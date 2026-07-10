from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request

from app.api.routes import (
    applications,
    audit,
    chat,
    health,
    jobs,
    operations,
    privacy,
    reports,
    resumes,
    usage,
)
from app.core.config import Settings, get_cached_settings
from app.core.logging import configure_logging
from app.core.production import validate_production_settings
from app.db.session import create_database_engine, create_session_factory, initialize_database


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_cached_settings()
    validate_production_settings(app_settings)
    configure_logging(app_settings.debug)
    app_settings.data_dir.mkdir(parents=True, exist_ok=True)
    app_settings.upload_dir.mkdir(parents=True, exist_ok=True)
    app_settings.export_dir.mkdir(parents=True, exist_ok=True)

    engine = create_database_engine(app_settings)
    if app_settings.create_db_schema_on_startup:
        initialize_database(engine)
    session_factory = create_session_factory(engine)

    app = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        description="Evidence-backed job application copilot API.",
    )
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        inbound_request_id = request.headers.get("x-request-id", "").strip()
        request_id = inbound_request_id if _is_safe_request_id(inbound_request_id) else str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    app.include_router(health.router)
    app.include_router(applications.router)
    app.include_router(resumes.router)
    app.include_router(jobs.router)
    app.include_router(operations.router)
    app.include_router(reports.router)
    app.include_router(chat.router)
    app.include_router(audit.router)
    app.include_router(privacy.router)
    app.include_router(usage.router)
    return app


def _is_safe_request_id(value: str) -> bool:
    return 8 <= len(value) <= 128 and all(
        character.isalnum() or character in "-_.:" for character in value
    )


app = create_app()


def run() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
