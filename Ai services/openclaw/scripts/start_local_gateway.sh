#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCLAW_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$OPENCLAW_DIR/../.." && pwd)"
WORKSPACE_DIR="$OPENCLAW_DIR/workspace"
LOCAL_DIR="$OPENCLAW_DIR/.local"
LOCAL_ENV_FILE="$LOCAL_DIR/openclaw-gateway.env"
BACKEND_ENV_FILE="$REPO_ROOT/Backend/.env"

RESUMEPILOT_API_BASE_URL="${RESUMEPILOT_API_BASE_URL:-http://127.0.0.1:8002}"
OPENCLAW_SENDER_ID="${OPENCLAW_SENDER_ID:-openclaw:local}"
OPENCLAW_SESSION_ID="${OPENCLAW_SESSION_ID:-openclaw:resume-pilot}"
OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"

ensure_path() {
  if command -v openclaw >/dev/null 2>&1; then
    return
  fi

  for candidate in "$HOME/.nvm/versions/node/v24.16.0/bin" "/opt/homebrew/bin"; do
    if [ -d "$candidate" ]; then
      PATH="$candidate:$PATH"
    fi
  done

  export PATH
}

load_env_file() {
  local env_file="$1"
  if [ -f "$env_file" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$env_file"
    set +a
  fi
}

load_existing_gateway_token() {
  if [ -n "${OPENCLAW_GATEWAY_TOKEN:-}" ] || [ ! -f "$LOCAL_ENV_FILE" ]; then
    return
  fi

  local token_line
  token_line="$(grep -E '^OPENCLAW_GATEWAY_TOKEN=' "$LOCAL_ENV_FILE" | tail -n 1 || true)"
  if [ -n "$token_line" ]; then
    OPENCLAW_GATEWAY_TOKEN="${token_line#OPENCLAW_GATEWAY_TOKEN=}"
  fi
}

generate_token() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
    return
  fi

  python3 - <<'PY'
import secrets

print(secrets.token_urlsafe(48))
PY
}

write_env_var() {
  local key="$1"
  local value="$2"

  printf '%s=%q\n' "$key" "$value"
}

detect_project() {
  if [ -n "$VERTEX_PROJECT_ID" ]; then
    printf '%s\n' "$VERTEX_PROJECT_ID"
    return
  fi

  if [ -n "${GOOGLE_CLOUD_PROJECT:-}" ]; then
    printf '%s\n' "$GOOGLE_CLOUD_PROJECT"
    return
  fi

  if command -v gcloud >/dev/null 2>&1; then
    local configured_project
    configured_project="$(gcloud config get-value project 2>/dev/null || true)"
    if [ -n "$configured_project" ] && [ "$configured_project" != "(unset)" ]; then
      printf '%s\n' "$configured_project"
      return
    fi
  fi
}

ensure_path
load_env_file "$BACKEND_ENV_FILE"
load_existing_gateway_token

LLM_PROVIDER="${LLM_PROVIDER:-vertex}"
LLM_MODEL="${LLM_MODEL:-gemini-3.5-flash}"
VERTEX_REGION="${VERTEX_REGION:-${GOOGLE_CLOUD_LOCATION:-global}}"
VERTEX_PROJECT_ID="${VERTEX_PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}"
OPENCLAW_MODEL_REFERENCE="${OPENCLAW_MODEL_REFERENCE:-google-vertex/$LLM_MODEL}"
GOOGLE_CLOUD_LOCATION="$VERTEX_REGION"

if [ "$LLM_PROVIDER" != "vertex" ]; then
  echo "This script supports LLM_PROVIDER=vertex for OpenClaw google-vertex setup." >&2
  exit 1
fi

if ! command -v openclaw >/dev/null 2>&1; then
  echo "OpenClaw CLI was not found. Install it with: curl -fsSL https://openclaw.ai/install.sh | bash" >&2
  exit 1
fi

if [ -z "${JOBCOPILOT_API_TOKEN:-}" ]; then
  echo "JOBCOPILOT_API_TOKEN is required so the /job skill can call ResumePilot." >&2
  echo "Set it in Backend/.env or export it in the current shell." >&2
  exit 1
fi

GOOGLE_CLOUD_PROJECT="$(detect_project)"
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
  echo "GOOGLE_CLOUD_PROJECT is required for google-vertex." >&2
  echo "Set it explicitly or run: gcloud config set project <project-id>" >&2
  exit 1
fi

if [ -z "${OPENCLAW_GATEWAY_TOKEN:-}" ]; then
  OPENCLAW_GATEWAY_TOKEN="$(generate_token)"
fi

mkdir -p "$LOCAL_DIR"
chmod 700 "$LOCAL_DIR"
umask 077
{
  write_env_var RESUMEPILOT_API_BASE_URL "$RESUMEPILOT_API_BASE_URL"
  write_env_var OPENCLAW_WORKSPACE_DIR "$WORKSPACE_DIR"
  write_env_var OPENCLAW_SENDER_ID "$OPENCLAW_SENDER_ID"
  write_env_var OPENCLAW_SESSION_ID "$OPENCLAW_SESSION_ID"
  write_env_var OPENCLAW_GATEWAY_PORT "$OPENCLAW_GATEWAY_PORT"
  write_env_var LLM_PROVIDER "$LLM_PROVIDER"
  write_env_var VERTEX_PROJECT_ID "$GOOGLE_CLOUD_PROJECT"
  write_env_var VERTEX_REGION "$GOOGLE_CLOUD_LOCATION"
  write_env_var LLM_MODEL "$LLM_MODEL"
  write_env_var OPENCLAW_MODEL_REFERENCE "$OPENCLAW_MODEL_REFERENCE"
  write_env_var OPENCLAW_GATEWAY_TOKEN "$OPENCLAW_GATEWAY_TOKEN"
  write_env_var GOOGLE_CLOUD_PROJECT "$GOOGLE_CLOUD_PROJECT"
  write_env_var GOOGLE_CLOUD_PROJECT_ID "$GOOGLE_CLOUD_PROJECT"
  write_env_var GOOGLE_CLOUD_LOCATION "$GOOGLE_CLOUD_LOCATION"
} >"$LOCAL_ENV_FILE"

export RESUMEPILOT_API_BASE_URL
export OPENCLAW_WORKSPACE_DIR="$WORKSPACE_DIR"
export OPENCLAW_SENDER_ID
export OPENCLAW_SESSION_ID
export OPENCLAW_GATEWAY_TOKEN
export GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
export GOOGLE_CLOUD_LOCATION
export VERTEX_PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
export VERTEX_REGION="$GOOGLE_CLOUD_LOCATION"
export LLM_PROVIDER
export LLM_MODEL

echo "Starting OpenClaw Gateway for ResumePilot..."
echo "Dashboard: http://127.0.0.1:$OPENCLAW_GATEWAY_PORT/"
echo "Local gateway env: $LOCAL_ENV_FILE"
echo "Token is stored locally and not printed."

exec openclaw gateway run \
  --allow-unconfigured \
  --bind loopback \
  --auth token \
  --port "$OPENCLAW_GATEWAY_PORT" \
  --token "$OPENCLAW_GATEWAY_TOKEN"
