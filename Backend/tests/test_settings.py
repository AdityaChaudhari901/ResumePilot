from app.core.config import Settings


def test_vertex_llm_settings_are_loaded_from_env_names(tmp_path):
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'resumepilot-test.db'}",
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
        LLM_PROVIDER="vertex",
        VERTEX_PROJECT_ID="alien-slice-499511-f8",
        VERTEX_REGION="global",
        LLM_MODEL="gemini-3.5-flash",
    )

    assert settings.llm_provider == "vertex"
    assert settings.vertex_project_id == "alien-slice-499511-f8"
    assert settings.vertex_region == "global"
    assert settings.llm_model == "gemini-3.5-flash"
