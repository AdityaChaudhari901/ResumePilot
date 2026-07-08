import uvicorn
from fastapi import FastAPI

from app.api.routes import audit, chat, health, jobs, privacy, reports, resumes, usage
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

    app.include_router(health.router)
    app.include_router(resumes.router)
    app.include_router(jobs.router)
    app.include_router(reports.router)
    app.include_router(chat.router)
    app.include_router(audit.router)
    app.include_router(privacy.router)
    app.include_router(usage.router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
