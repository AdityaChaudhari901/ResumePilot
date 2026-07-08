from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'resumepilot-test.db'}",
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
        JOBCOPILOT_API_TOKEN="test-token",
        OPENCLAW_SENDER_ALLOWLIST="telegram:12345",
    )


@pytest.fixture
def client(settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_resume_text() -> str:
    return """Aarav Sharma
aarav@example.com
https://github.com/aarav

Skills
Python, FastAPI, PostgreSQL, SQLAlchemy, REST APIs, Pytest, Git

Projects
Built a Python FastAPI backend with PostgreSQL, SQLAlchemy, and JWT authentication.
Implemented REST API endpoints and pytest coverage for a job tracking project.

Education
B.Tech Computer Science
"""


@pytest.fixture
def sample_job_text() -> str:
    return """Role: Junior Backend Engineer
Company: NovaHire AI

Responsibilities:
- Build REST API services for AI-powered hiring workflows.
- Improve backend reliability and test coverage.

Requirements:
- Required Python experience.
- Required FastAPI or similar API framework experience.
- Required REST API service development experience.
- Required SQL database experience.
- Preferred Docker experience.

Experience: 0-2 years.
"""
