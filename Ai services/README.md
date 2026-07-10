# AI Services

Contains OpenClaw channel assets and notes for LLM-facing workflows.

Current status:

- Runtime agent workflow code lives in `Backend/app/services/agent_workflow.py` so it can share the backend's strict schemas, matcher, report generator, and validation gate.
- `Backend/app/schemas/agent.py` defines the structured contracts for each agent step.
- `Backend/app/services/langgraph_workflow.py` owns the resumable live-draft graph; LangChain model calls appear only inside its generation nodes.
- `openclaw/` contains the project-local OpenClaw workspace and `/job` skill that calls the backend `/chat/openclaw` endpoint.

Responsibilities for this folder:

- OpenClaw onboarding notes and channel-specific setup.
- Channel scripts that call FastAPI without owning workflow or tenant state.

The deterministic backend remains the source of truth. Agents must operate on structured evidence and validated schemas only.
