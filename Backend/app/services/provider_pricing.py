from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from importlib.resources import files

from pydantic import Field

from app.schemas.agent import AgentTokenUsage
from app.schemas.common import StrictBaseModel

_COST_PRECISION = Decimal("0.00000001")


class ProviderPricingRate(StrictBaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_aliases: list[str] = Field(default_factory=list)
    canonical_model: str = Field(min_length=1)
    region: str = Field(min_length=1)
    pricing_tier: str = Field(min_length=1)
    input_per_1m_tokens_usd: Decimal = Field(ge=0)
    output_per_1m_tokens_usd: Decimal = Field(ge=0)
    cached_input_per_1m_tokens_usd: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class ProviderPricingConfig(StrictBaseModel):
    version: str = Field(min_length=1)
    verified_on: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    unit_tokens: int = Field(gt=0)
    rates: list[ProviderPricingRate] = Field(min_length=1)


class ProviderCostEstimate(StrictBaseModel):
    amount_usd: float = Field(ge=0)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


def estimate_provider_cost(
    *,
    provider: str | None,
    model: str | None,
    region: str | None,
    token_usage: AgentTokenUsage | None,
) -> ProviderCostEstimate | None:
    """Estimate provider cost from configured pricing and reported token usage.

    The function returns no estimate unless provider/model/region match a configured
    rate and CrewAI exposed enough token detail to separate input from output tokens.
    """

    if token_usage is None:
        return None

    rate = _find_rate(provider=provider, model=model, region=region)
    if rate is None:
        return None

    input_tokens = token_usage.prompt_tokens
    output_tokens = token_usage.completion_tokens
    if output_tokens == 0 and token_usage.reasoning_tokens > 0:
        output_tokens = token_usage.reasoning_tokens
    if input_tokens == 0 and output_tokens == 0:
        return None

    cached_input_tokens = 0
    uncached_input_tokens = input_tokens
    if token_usage.cached_prompt_tokens > 0 and rate.cached_input_per_1m_tokens_usd is not None:
        cached_input_tokens = min(token_usage.cached_prompt_tokens, input_tokens)
        uncached_input_tokens = max(input_tokens - cached_input_tokens, 0)

    config = provider_pricing_config()
    unit_tokens = Decimal(config.unit_tokens)
    cost = (
        Decimal(uncached_input_tokens) * rate.input_per_1m_tokens_usd
        + Decimal(output_tokens) * rate.output_per_1m_tokens_usd
        + Decimal(cached_input_tokens) * (rate.cached_input_per_1m_tokens_usd or Decimal("0"))
    ) / unit_tokens
    amount = float(cost.quantize(_COST_PRECISION, rounding=ROUND_HALF_UP))

    return ProviderCostEstimate(
        amount_usd=amount,
        metadata={
            "cost_estimate_source": "provider_pricing_config",
            "pricing_version": config.version,
            "pricing_verified_on": config.verified_on,
            "pricing_source_url": config.source_url,
            "pricing_currency": config.currency,
            "pricing_unit_tokens": config.unit_tokens,
            "pricing_provider": rate.provider,
            "pricing_model": rate.model,
            "pricing_canonical_model": rate.canonical_model,
            "pricing_region": rate.region,
            "pricing_tier": rate.pricing_tier,
            "pricing_input_per_1m_tokens_usd": float(rate.input_per_1m_tokens_usd),
            "pricing_output_per_1m_tokens_usd": float(rate.output_per_1m_tokens_usd),
            "pricing_cached_input_per_1m_tokens_usd": (
                float(rate.cached_input_per_1m_tokens_usd)
                if rate.cached_input_per_1m_tokens_usd is not None
                else None
            ),
            "billable_input_tokens": uncached_input_tokens,
            "billable_cached_input_tokens": cached_input_tokens,
            "billable_output_tokens": output_tokens,
        },
    )


@lru_cache
def provider_pricing_config() -> ProviderPricingConfig:
    pricing_path = files("app.data").joinpath("provider_pricing.json")
    return ProviderPricingConfig.model_validate_json(pricing_path.read_text(encoding="utf-8"))


def _find_rate(
    *,
    provider: str | None,
    model: str | None,
    region: str | None,
) -> ProviderPricingRate | None:
    if provider is None or model is None or region is None:
        return None

    normalized_provider = _normalize_provider(provider)
    normalized_region = _normalize_text(region)
    requested_models = _model_keys(model)
    for rate in provider_pricing_config().rates:
        if _normalize_provider(rate.provider) != normalized_provider:
            continue
        if _normalize_text(rate.region) != normalized_region:
            continue
        rate_models = _model_keys(rate.model)
        for alias in rate.model_aliases:
            rate_models.update(_model_keys(alias))
        if requested_models & rate_models:
            return rate
    return None


def _normalize_provider(value: str) -> str:
    normalized = _normalize_text(value).replace("_", "-")
    if normalized in {"vertex-ai", "vertexai", "google-vertex"}:
        return "vertex"
    return normalized


def _model_keys(value: str) -> set[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return set()

    suffix = normalized.rsplit("/", maxsplit=1)[-1]
    keys = {normalized, suffix}
    if suffix:
        keys.add(f"google/{suffix}")
        keys.add(f"google-vertex/{suffix}")
    return keys


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())
