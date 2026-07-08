# ResumePilot OpenClaw Integration

This folder contains the project-local OpenClaw workspace for the ResumePilot `/job` command.

The integration follows the OpenClaw docs for workspace skills:

- Skills live under a workspace `skills/` directory.
- A skill is a folder with `SKILL.md`.
- User-invocable skills can be called with `/skill <name> [input]`; native skill commands can expose the skill name directly, such as `/job`.

## Prerequisites

Install OpenClaw:

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

The implementation was verified with:

```text
OpenClaw 2026.6.11
Node.js v24.16.0
```

## Start ResumePilot API

From `Backend/`:

```bash
source .venv/bin/activate
cp .env.example .env
export JOBCOPILOT_API_TOKEN="replace-with-local-token"
export OPENCLAW_SENDER_ALLOWLIST="openclaw:local,telegram:12345"
uvicorn app.main:app --host 127.0.0.1 --port 8002
```

## Use This Workspace

Point OpenClaw at this project-local workspace:

```bash
export OPENCLAW_WORKSPACE_DIR="$PWD/Ai services/openclaw/workspace"
export RESUMEPILOT_API_BASE_URL="http://127.0.0.1:8002"
export JOBCOPILOT_API_TOKEN="replace-with-local-token"
export OPENCLAW_SENDER_ID="openclaw:local"
export OPENCLAW_SESSION_ID="openclaw:resume-pilot"
```

Verify the skill:

```bash
openclaw skills list --eligible
openclaw skills info job
openclaw skills check
```

## Google Vertex Provider

ResumePilot can use OpenClaw's Google Vertex model provider for the local Gateway. Current OpenClaw docs identify the provider as `google-vertex` and use Google Cloud Application Default Credentials for auth.

Local prerequisite:

```bash
gcloud auth application-default login
gcloud config set project <gcp-project-id>
export GOOGLE_CLOUD_PROJECT=<gcp-project-id>
export GOOGLE_CLOUD_LOCATION=us-central1
```

Enable the included Google plugin and set the default model reference after choosing a Vertex model available in your project and region:

```bash
./Ai\ services/openclaw/scripts/configure_vertex_gateway.sh
```

The script enables the included Google plugin, sets the default model reference, points OpenClaw at the project-local workspace, keeps the Gateway on loopback, and validates the config. Override defaults when needed:

```bash
OPENCLAW_MODEL_REFERENCE=google-vertex/gemini-2.5-flash \
GOOGLE_CLOUD_LOCATION=us-central1 \
./Ai\ services/openclaw/scripts/configure_vertex_gateway.sh
```

The current demo default is `google-vertex/gemini-2.5-flash`. Use a stable model ID for demos when possible. Confirm availability in your Google Cloud project and region before relying on it for a recorded demo.

## WebChat / Control UI

Start the Gateway locally and open the browser dashboard:

```bash
./Ai\ services/openclaw/scripts/start_local_gateway.sh
```

Default local dashboard:

```text
http://127.0.0.1:18789/
```

The Control UI is an admin surface. Keep it on loopback, Tailscale, or an SSH tunnel; do not expose it publicly.

The start script creates `Ai services/openclaw/.local/openclaw-gateway.env` with a generated gateway token and local runtime settings. The file is ignored by Git and should stay on the local machine. In a second shell, load it before opening the dashboard:

```bash
set -a
source "./Ai services/openclaw/.local/openclaw-gateway.env"
set +a
openclaw dashboard
```

If OpenClaw reports `scope upgrade pending approval` for the local CLI, approve the pending device request from the Control UI or run the `openclaw devices approve <request-id>` command printed by OpenClaw with the local gateway token loaded in the shell. Do not disable gateway token auth to work around pairing.

Run from OpenClaw chat:

```text
/job https://company.com/jobs/software-engineer
/job paste:Role: Backend Engineer...
/skill job paste:Role: Backend Engineer...
```

## Local Helper Smoke Test

You can bypass chat and call the same backend endpoint directly:

```bash
python3 "Ai services/openclaw/workspace/skills/job/scripts/resumepilot_job.py" \
  "paste:Role: Backend Engineer
Company: NovaHire AI
Requirements:
- Required Python experience.
- Required FastAPI experience.
- Required SQL database experience.
Responsibilities:
- Build REST API services for hiring workflows."
```

## Security Notes

- Keep `JOBCOPILOT_API_TOKEN` in local environment or OpenClaw config, not in Git.
- Keep ResumePilot API bound to loopback during MVP demos.
- Keep `OPENCLAW_SENDER_ALLOWLIST` narrow.
- Do not use this local gateway as a shared multi-user boundary.
