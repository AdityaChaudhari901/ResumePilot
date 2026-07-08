#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_PROVIDER = "google-vertex"
DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_REGION = "global"
DEFAULT_CONTEXT_TOKENS = 1_048_576
DEFAULT_MAX_TOKENS = 65_536


def main() -> int:
    provider = os.environ.get("OPENCLAW_PROVIDER", DEFAULT_PROVIDER).strip() or DEFAULT_PROVIDER
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    model_reference = (
        os.environ.get("OPENCLAW_MODEL_REFERENCE", f"{provider}/{model}").strip()
        or f"{provider}/{model}"
    )
    model_id = model_reference.split("/", 1)[1] if "/" in model_reference else model
    project_id = (
        os.environ.get("VERTEX_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT_ID")
        or ""
    ).strip()
    region = (
        os.environ.get("VERTEX_REGION")
        or os.environ.get("GOOGLE_CLOUD_LOCATION")
        or DEFAULT_REGION
    ).strip()

    openclaw_home = Path(os.environ.get("OPENCLAW_HOME", Path.home() / ".openclaw"))
    config_path = Path(
        os.environ.get("OPENCLAW_CONFIG_FILE", openclaw_home / "openclaw.json")
    ).expanduser()
    agent_id = os.environ.get("OPENCLAW_AGENT_ID", "main").strip() or "main"
    agent_models_path = Path(
        os.environ.get(
            "OPENCLAW_AGENT_MODELS_FILE",
            openclaw_home / "agents" / agent_id / "agent" / "models.json",
        )
    ).expanduser()

    provider_config = build_provider_config(
        provider=provider,
        model_id=model_id,
        project_id=project_id,
        region=region,
    )

    update_global_config(config_path, provider, model_reference, provider_config)
    update_agent_models(agent_models_path, provider, provider_config)

    print(f"Registered OpenClaw model provider: {model_reference}")
    print(f"Global config: {config_path}")
    print(f"Agent model registry: {agent_models_path}")
    return 0


def build_provider_config(
    *,
    provider: str,
    model_id: str,
    project_id: str,
    region: str,
) -> dict[str, Any]:
    model_entry = {
        "id": model_id,
        "name": humanize_model_name(model_id),
        "api": provider,
        "input": ["text", "image"],
        "contextWindow": DEFAULT_CONTEXT_TOKENS,
        "contextTokens": DEFAULT_CONTEXT_TOKENS,
        "maxTokens": DEFAULT_MAX_TOKENS,
    }
    params: dict[str, str] = {"location": region}
    if project_id:
        params["project"] = project_id

    return {
        "api": provider,
        "region": region,
        "contextWindow": DEFAULT_CONTEXT_TOKENS,
        "contextTokens": DEFAULT_CONTEXT_TOKENS,
        "models": [model_entry],
        "apiKey": "gcp-vertex-credentials",
        "params": params,
    }


def update_global_config(
    path: Path,
    provider: str,
    model_reference: str,
    provider_config: dict[str, Any],
) -> None:
    config = read_json_object(path)
    models = ensure_object(config, "models")
    providers = ensure_object(models, "providers")
    providers[provider] = merge_provider(providers.get(provider), provider_config)

    agents = ensure_object(config, "agents")
    defaults = ensure_object(agents, "defaults")
    model_default = ensure_object(defaults, "model")
    model_default["primary"] = model_reference
    allowed_models = ensure_object(defaults, "models")
    allowed_models.setdefault(model_reference, {})

    write_json_object(path, config)


def update_agent_models(path: Path, provider: str, provider_config: dict[str, Any]) -> None:
    config = read_json_object(path)
    providers = ensure_object(config, "providers")
    providers[provider] = merge_provider(providers.get(provider), provider_config)
    write_json_object(path, config)


def merge_provider(existing: Any, replacement: dict[str, Any]) -> dict[str, Any]:
    base = dict(existing) if isinstance(existing, dict) else {}
    base.update({key: value for key, value in replacement.items() if key != "models"})

    existing_models = base.get("models")
    models = list(existing_models) if isinstance(existing_models, list) else []
    replacement_models = replacement.get("models", [])
    for new_model in replacement_models:
        new_id = new_model.get("id") if isinstance(new_model, dict) else None
        models = [
            model
            for model in models
            if not (isinstance(model, dict) and model.get("id") == new_id)
        ]
        models.append(new_model)
    base["models"] = models
    return base


def ensure_object(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        value = {}
        parent[key] = value
    return value


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"Expected JSON object in {path}.")
    return value


def write_json_object(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temp_path, 0o600)
    temp_path.replace(path)


def humanize_model_name(model_id: str) -> str:
    parts = []
    for part in model_id.replace("_", "-").split("-"):
        if part.lower() == "gemini":
            parts.append("Gemini")
        elif part.lower() == "flash":
            parts.append("Flash")
        elif part.lower() == "pro":
            parts.append("Pro")
        else:
            parts.append(part)
    return " ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
