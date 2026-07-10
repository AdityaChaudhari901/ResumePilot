import json
import os
import sys
from time import perf_counter
from typing import Any

from pydantic import Field

from app.core.config import Settings
from app.schemas.agent import (
    AgentStepName,
    AgentTokenUsage,
    CoverLetterAgentOutput,
    InterviewCoachAgentOutput,
    ResumeMatchAgentOutput,
)
from app.schemas.common import StrictBaseModel
from app.schemas.job import JobProfile
from app.schemas.match import MatchResult
from app.schemas.report import ApplicationReport
from app.schemas.resume import ResumeProfile


class CrewAIWorkflowUnavailable(RuntimeError):
    """Raised when live CrewAI execution cannot be used in the current runtime."""


class CrewAIWorkflowSections(StrictBaseModel):
    resume_match: ResumeMatchAgentOutput
    cover_letter: CoverLetterAgentOutput
    interview_coach: InterviewCoachAgentOutput
    step_durations_ms: dict[str, int] = Field(default_factory=dict)
    token_usage: AgentTokenUsage | None = None


class CrewAIWorkflowRunner:
    """Bounded CrewAI runner that rewrites only explain/draft sections."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._agent_cls: type[Any] | None = None
        self._llm: Any | None = None

    def run(
        self,
        *,
        resume: ResumeProfile,
        job: JobProfile,
        match: MatchResult,
        deterministic_report: ApplicationReport,
    ) -> CrewAIWorkflowSections:
        self._prepare_runtime()
        step_durations_ms: dict[str, int] = {}

        resume_match_started_at = perf_counter()
        resume_match = self._run_agent(
            role="Evidence-bound resume match analyst",
            goal=(
                "Explain the deterministic resume/job match in concise, useful language "
                "without changing the score, missing skills, or evidence."
            ),
            response_format=ResumeMatchAgentOutput,
            prompt=self._prompt(
                "Resume Match Agent",
                [
                    "Explain fit using only deterministic input.",
                    "Do not add skills or evidence IDs.",
                    "Keep confidence aligned to the deterministic match confidence.",
                ],
                resume=resume,
                job=job,
                match=match,
                deterministic_report=deterministic_report,
            ),
        )
        step_durations_ms[AgentStepName.resume_match.value] = _elapsed_ms(resume_match_started_at)

        cover_letter_started_at = perf_counter()
        cover_letter = self._run_agent(
            role="Evidence-bound cover letter writer",
            goal=(
                "Draft a concise cover letter from validated fit evidence only, with a "
                "clear confidence note."
            ),
            response_format=CoverLetterAgentOutput,
            prompt=self._prompt(
                "Cover Letter Agent",
                [
                    "Keep the letter under 300 words.",
                    "Use only supported resume evidence and matched skills.",
                    "Avoid exaggerated claims such as perfect fit unless the score is very high.",
                    "Return evidence IDs that support the draft.",
                ],
                resume=resume,
                job=job,
                match=match,
                deterministic_report=deterministic_report,
            ),
        )
        step_durations_ms[AgentStepName.cover_letter.value] = _elapsed_ms(cover_letter_started_at)

        interview_coach_started_at = perf_counter()
        interview_coach = self._run_agent(
            role="Evidence-bound interview coach",
            goal=(
                "Generate targeted interview preparation grouped by technical, behavioral, "
                "project, and gap-focused categories."
            ),
            response_format=InterviewCoachAgentOutput,
            prompt=self._prompt(
                "Interview Coach Agent",
                [
                    "Tie suggested answer evidence IDs to resume facts.",
                    "Flag weak and missing areas honestly.",
                    "Do not invent projects, employers, metrics, degrees, or certifications.",
                ],
                resume=resume,
                job=job,
                match=match,
                deterministic_report=deterministic_report,
            ),
        )
        step_durations_ms[AgentStepName.interview_coach.value] = _elapsed_ms(
            interview_coach_started_at
        )

        return CrewAIWorkflowSections(
            resume_match=resume_match,
            cover_letter=cover_letter,
            interview_coach=interview_coach,
            step_durations_ms=step_durations_ms,
            token_usage=_extract_token_usage(self._llm),
        )

    def _prepare_runtime(self) -> None:
        if self._agent_cls is not None and self._llm is not None:
            return
        if sys.version_info >= (3, 14):
            raise CrewAIWorkflowUnavailable(
                "CrewAI requires Python >=3.10,<3.14; current runtime is "
                f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}."
            )

        try:
            from crewai import LLM, Agent
        except ImportError as exc:
            raise CrewAIWorkflowUnavailable(
                "CrewAI is not installed. Install the backend with the ai extra on Python 3.12 "
                'or 3.13: python -m pip install -e ".[dev,ai]".'
            ) from exc

        self._prepare_provider_environment()
        self._agent_cls = Agent
        self._llm = LLM(
            model=_crewai_model_reference(self._settings),
            temperature=self._settings.crewai_temperature,
        )

    def _prepare_provider_environment(self) -> None:
        if self._settings.llm_provider.strip().lower() != "vertex":
            return
        if not self._settings.vertex_project_id:
            raise CrewAIWorkflowUnavailable(
                "VERTEX_PROJECT_ID is required when LLM_PROVIDER=vertex and "
                "AGENT_WORKFLOW_MODE=crewai."
            )
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", self._settings.vertex_project_id)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", self._settings.vertex_region)

    def _run_agent[OutputModelT: StrictBaseModel](
        self,
        *,
        role: str,
        goal: str,
        response_format: type[OutputModelT],
        prompt: str,
    ) -> OutputModelT:
        if self._agent_cls is None or self._llm is None:
            raise CrewAIWorkflowUnavailable("CrewAI runtime was not initialized.")

        agent = self._agent_cls(
            role=role,
            goal=goal,
            backstory=(
                "You are a ResumePilot agent. Deterministic resume parsing, job parsing, "
                "matching, and validation are the source of truth."
            ),
            llm=self._llm,
            allow_delegation=False,
            max_iter=self._settings.crewai_max_iter,
            max_execution_time=self._settings.crewai_timeout_seconds,
        )
        output = agent.kickoff(prompt, response_format=response_format)
        return _coerce_pydantic_output(output, response_format)

    def _prompt(
        self,
        step_name: str,
        rules: list[str],
        *,
        resume: ResumeProfile,
        job: JobProfile,
        match: MatchResult,
        deterministic_report: ApplicationReport,
    ) -> str:
        payload = {
            "step": step_name,
            "rules": [
                "Return only data that fits the requested Pydantic response format.",
                "Resume evidence IDs are the only allowed support references.",
                "Never invent work history, skills, employers, metrics, certifications, or "
                "degrees.",
                *rules,
            ],
            "resume": _llm_safe_resume_payload(resume),
            "job": job.model_dump(mode="json"),
            "deterministic_match": match.model_dump(mode="json"),
            "deterministic_report": deterministic_report.model_dump(
                mode="json",
                exclude={"cover_letter", "resume_candidate_name"},
            ),
        }
        private_replacements = {
            str(value): "Candidate" if value == resume.candidate.name else "[redacted]"
            for value in (
                resume.candidate.name,
                resume.candidate.email,
                resume.candidate.phone,
                *resume.candidate.links,
            )
            if value and str(value).strip()
        }
        payload = _redact_private_values(payload, private_replacements)
        return json.dumps(payload, ensure_ascii=True)


def build_crewai_workflow_runner(settings: Settings) -> CrewAIWorkflowRunner:
    return CrewAIWorkflowRunner(settings)


def _llm_safe_resume_payload(resume: ResumeProfile) -> dict[str, Any]:
    payload = resume.model_dump(
        mode="json",
        exclude={"candidate"},
    )
    private_values = {
        str(value).strip().casefold()
        for value in (
            resume.candidate.name,
            resume.candidate.email,
            resume.candidate.phone,
            *resume.candidate.links,
        )
        if value and str(value).strip()
    }
    for section in ("facts", "experience", "projects", "education", "certifications"):
        entries = payload.get(section)
        if not isinstance(entries, list):
            continue
        payload[section] = [
            entry
            for entry in entries
            if not (
                isinstance(entry, dict)
                and str(entry.get("text", "")).strip().casefold() in private_values
            )
        ]
    return payload


def _redact_private_values(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _redact_private_values(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_private_values(item, replacements) for item in value]
    if isinstance(value, str):
        redacted = value
        for private_value, replacement in replacements.items():
            redacted = redacted.replace(private_value, replacement)
        return redacted
    return value


def _crewai_model_reference(settings: Settings) -> str:
    if settings.crewai_llm_model:
        return settings.crewai_llm_model
    if settings.llm_provider.strip().lower() == "vertex":
        return f"google/{settings.llm_model}"
    return settings.llm_model


def _coerce_pydantic_output[OutputModelT: StrictBaseModel](
    output: Any,
    response_format: type[OutputModelT],
) -> OutputModelT:
    parsed = getattr(output, "pydantic", None)
    if parsed is not None:
        return response_format.model_validate(parsed)

    raw = getattr(output, "raw", None)
    if isinstance(raw, str):
        return response_format.model_validate_json(raw)
    if isinstance(output, str):
        return response_format.model_validate_json(output)

    raise CrewAIWorkflowUnavailable(
        f"CrewAI returned no typed output for {response_format.__name__}."
    )


def _extract_token_usage(llm: Any | None) -> AgentTokenUsage | None:
    if llm is None or not hasattr(llm, "get_token_usage_summary"):
        return None

    usage = llm.get_token_usage_summary()
    if usage is None:
        return None

    if hasattr(usage, "model_dump"):
        usage_data = usage.model_dump()
    elif isinstance(usage, dict):
        usage_data = usage
    else:
        return None

    token_usage = AgentTokenUsage.model_validate(
        {field: usage_data.get(field, 0) for field in AgentTokenUsage.model_fields}
    )
    if token_usage.total_tokens == 0 and token_usage.successful_requests == 0:
        return None
    return token_usage


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))
