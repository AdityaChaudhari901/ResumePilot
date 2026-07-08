import pytest

from app.schemas.agent import AgentTokenUsage
from app.services.provider_pricing import estimate_provider_cost, provider_pricing_config


def test_provider_pricing_config_loads_vertex_global_gemini_flash_rate():
    config = provider_pricing_config()

    assert config.version == "2026-07-08.vertex-global-standard.v1"
    assert config.currency == "USD"
    assert config.unit_tokens == 1_000_000
    assert config.rates[0].provider == "vertex"
    assert config.rates[0].canonical_model == "gemini-3.5-flash"


def test_estimate_provider_cost_for_vertex_gemini_flash_tokens():
    estimate = estimate_provider_cost(
        provider="vertex",
        model="google/gemini-3.5-flash",
        region="global",
        token_usage=AgentTokenUsage(
            total_tokens=9997,
            prompt_tokens=9052,
            completion_tokens=945,
            successful_requests=3,
        ),
    )

    assert estimate is not None
    assert estimate.amount_usd == pytest.approx(0.022083)
    assert estimate.metadata["cost_estimate_source"] == "provider_pricing_config"
    assert estimate.metadata["pricing_input_per_1m_tokens_usd"] == 1.5
    assert estimate.metadata["pricing_output_per_1m_tokens_usd"] == 9.0
    assert estimate.metadata["billable_input_tokens"] == 9052
    assert estimate.metadata["billable_output_tokens"] == 945


def test_estimate_provider_cost_accounts_for_cached_prompt_tokens():
    estimate = estimate_provider_cost(
        provider="google-vertex",
        model="google-vertex/gemini-3.5-flash",
        region="GLOBAL",
        token_usage=AgentTokenUsage(
            total_tokens=1100,
            prompt_tokens=1000,
            completion_tokens=100,
            cached_prompt_tokens=400,
            successful_requests=1,
        ),
    )

    assert estimate is not None
    assert estimate.amount_usd == pytest.approx(0.00186)
    assert estimate.metadata["billable_input_tokens"] == 600
    assert estimate.metadata["billable_cached_input_tokens"] == 400


def test_estimate_provider_cost_returns_none_for_unconfigured_rate():
    estimate = estimate_provider_cost(
        provider="vertex",
        model="google/gemini-unknown",
        region="global",
        token_usage=AgentTokenUsage(
            total_tokens=100,
            prompt_tokens=50,
            completion_tokens=50,
            successful_requests=1,
        ),
    )

    assert estimate is None


def test_estimate_provider_cost_returns_none_when_token_split_is_missing():
    estimate = estimate_provider_cost(
        provider="vertex",
        model="google/gemini-3.5-flash",
        region="global",
        token_usage=AgentTokenUsage(total_tokens=100, successful_requests=1),
    )

    assert estimate is None
