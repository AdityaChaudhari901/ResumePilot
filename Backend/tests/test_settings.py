from app.core.config import Settings
from app.schemas.agent import AgentWorkflowMode


def test_vertex_llm_settings_are_loaded_from_env_names(tmp_path):
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'resumepilot-test.db'}",
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
        LLM_PROVIDER="vertex",
        VERTEX_PROJECT_ID="alien-slice-499511-f8",
        VERTEX_REGION="global",
        LLM_MODEL="gemini-3.5-flash",
        AGENT_WORKFLOW_MODE="crewai",
        CREWAI_LLM_MODEL="google/gemini-3.5-flash",
        CREWAI_MAX_ITER=3,
        CREWAI_TIMEOUT_SECONDS=90,
        CREWAI_TEMPERATURE=0.1,
        LATEX_COMPILE_TIMEOUT_SECONDS=30,
        LATEX_PDF_MAX_BYTES=10485760,
        DATA_RETENTION_DAYS=30,
        ENABLE_JOB_BROWSER_FALLBACK=False,
        JOB_BROWSER_TIMEOUT_MS=12000,
    )

    assert settings.llm_provider == "vertex"
    assert settings.vertex_project_id == "alien-slice-499511-f8"
    assert settings.vertex_region == "global"
    assert settings.llm_model == "gemini-3.5-flash"
    assert settings.agent_workflow_mode == AgentWorkflowMode.crewai
    assert settings.crewai_llm_model == "google/gemini-3.5-flash"
    assert settings.crewai_max_iter == 3
    assert settings.crewai_timeout_seconds == 90
    assert settings.crewai_temperature == 0.1
    assert settings.latex_compile_timeout_seconds == 30
    assert settings.latex_pdf_max_bytes == 10485760
    assert settings.data_retention_days == 30
    assert settings.enable_job_browser_fallback is False
    assert settings.job_browser_timeout_ms == 12000


def test_empty_data_retention_days_disables_retention(tmp_path):
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'resumepilot-test.db'}",
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
        DATA_RETENTION_DAYS="",
    )

    assert settings.data_retention_days is None
