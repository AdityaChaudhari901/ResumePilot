#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCLAW_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$OPENCLAW_DIR/../.." && pwd)"
WORKSPACE_DIR="$OPENCLAW_DIR/workspace"

OPENCLAW_MODEL_REFERENCE="${OPENCLAW_MODEL_REFERENCE:-google-vertex/gemini-2.5-flash}"
OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
ADC_FILE="${GOOGLE_APPLICATION_CREDENTIALS:-$HOME/.config/gcloud/application_default_credentials.json}"

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

detect_project() {
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

  if [ -f "$ADC_FILE" ] && command -v python3 >/dev/null 2>&1; then
    python3 - "$ADC_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)

print(data.get("quota_project_id", ""))
PY
  fi
}

ensure_path

if ! command -v openclaw >/dev/null 2>&1; then
  echo "OpenClaw CLI was not found. Install it with: curl -fsSL https://openclaw.ai/install.sh | bash" >&2
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud CLI was not found. Install and initialize Google Cloud SDK before using google-vertex." >&2
  exit 1
fi

if [ ! -f "$ADC_FILE" ]; then
  echo "Google ADC file was not found at: $ADC_FILE" >&2
  echo "Run: gcloud auth application-default login" >&2
  exit 1
fi

GOOGLE_CLOUD_PROJECT="$(detect_project)"
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
  echo "No Google Cloud project found. Set GOOGLE_CLOUD_PROJECT or run: gcloud config set project <project-id>" >&2
  exit 1
fi
export GOOGLE_CLOUD_PROJECT
export GOOGLE_CLOUD_LOCATION

echo "Configuring OpenClaw for ResumePilot..."
openclaw plugins enable google
openclaw models set "$OPENCLAW_MODEL_REFERENCE"
openclaw config set gateway.mode local
openclaw config set gateway.bind loopback
openclaw config set gateway.port "$OPENCLAW_GATEWAY_PORT" --strict-json
openclaw config set gateway.auth.mode token
openclaw config set agents.defaults.workspace "$WORKSPACE_DIR"
openclaw config set agents.defaults.repoRoot "$REPO_ROOT"

if gcloud services list \
  --enabled \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --filter='name:aiplatform.googleapis.com' \
  --format='value(config.name)' 2>/dev/null | grep -q '^aiplatform.googleapis.com$'; then
  echo "Vertex AI API is enabled for the selected project."
else
  echo "Vertex AI API is not enabled or could not be verified." >&2
  echo "Run: gcloud services enable aiplatform.googleapis.com --project \"$GOOGLE_CLOUD_PROJECT\"" >&2
fi

openclaw config validate

echo "OpenClaw config is ready for ResumePilot."
echo "Workspace: $WORKSPACE_DIR"
echo "Model: $OPENCLAW_MODEL_REFERENCE"
echo "Dashboard: http://127.0.0.1:$OPENCLAW_GATEWAY_PORT/"
