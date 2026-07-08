# AI Services

Reserved for CrewAI and LLM-facing workflows.

Current status:

- Runtime agent workflow code lives in `Backend/app/services/agent_workflow.py` so it can share the backend's strict schemas, matcher, report generator, and validation gate.
- `Backend/app/schemas/agent.py` defines the structured contracts for each agent step.
- The current implementation is a deterministic fallback that mirrors the planned CrewAI sequence without requiring a live LLM key.
- `openclaw/` contains the project-local OpenClaw workspace and `/job` skill that calls the backend `/chat/openclaw` endpoint.

Planned responsibilities for this folder:

- CrewAI Flow wrapper.
- CrewAI/provider configuration.
- Prompt templates with explicit data boundaries.
- OpenClaw onboarding notes and channel-specific setup.
- Agent output validation and repair helpers.

The deterministic backend remains the source of truth. Agents must operate on structured evidence and validated schemas only.
