import json
from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.schemas.agent import (
    CoverLetterAgentOutput,
    InterviewCoachAgentOutput,
    ResumeMatchAgentOutput,
)
from app.schemas.operation import WorkflowApprovalDecision
from app.schemas.report import InterviewQuestionGroup
from app.services.agent_workflow import apply_approved_live_draft, run_application_agent_workflow
from app.services.job_parser import parse_job_profile
from app.services.langgraph_workflow import LiveDraftGraphRunner
from app.services.matcher import match_resume_to_job
from app.services.resume_parser import parse_resume_profile


@pytest.mark.parametrize(
    "decision",
    [WorkflowApprovalDecision.approve, WorkflowApprovalDecision.reject],
)
def test_live_draft_graph_interrupts_and_resumes_without_rerunning_model_nodes(
    decision,
    settings,
    sample_resume_text,
    sample_job_text,
):
    runner, model = _runner(
        settings,
        sample_resume_text,
        sample_job_text,
    )
    checkpointer = InMemorySaver()
    operation_id = f"00000000-0000-4000-8000-00000000000{1 if decision.value == 'approve' else 2}"

    paused = runner.start(
        operation_id=operation_id,
        analysis_id=41,
        checkpointer=checkpointer,
    )

    assert paused.paused is True
    assert paused.approval_decision is None
    assert len(paused.proposal_revision) == 64
    assert model.invoke_count == 3

    resumed = runner.resume(
        operation_id=operation_id,
        decision=decision,
        proposal_revision=paused.proposal_revision,
        checkpointer=checkpointer,
    )

    assert resumed.paused is False
    assert resumed.approval_decision == decision
    assert resumed.proposal_revision == paused.proposal_revision
    assert resumed.proposal == paused.proposal
    assert model.invoke_count == 3

    replayed = runner.resume(
        operation_id=operation_id,
        decision=decision,
        proposal_revision=paused.proposal_revision,
        checkpointer=checkpointer,
    )
    assert replayed.approval_decision == decision
    assert model.invoke_count == 3


def test_live_draft_revision_is_stable_and_checkpoint_excludes_private_source_input(
    settings,
    sample_resume_text,
    sample_job_text,
):
    first_runner, first_model = _runner(settings, sample_resume_text, sample_job_text)
    second_runner, _second_model = _runner(settings, sample_resume_text, sample_job_text)
    checkpointer = InMemorySaver()

    first = first_runner.start(
        operation_id="00000000-0000-4000-8000-000000000011",
        analysis_id=51,
        checkpointer=checkpointer,
    )
    second = second_runner.start(
        operation_id="00000000-0000-4000-8000-000000000012",
        analysis_id=52,
        checkpointer=checkpointer,
    )

    assert first.proposal_revision == second.proposal_revision
    graph = first_runner._compile(checkpointer)
    graph_config = {"configurable": {"thread_id": "00000000-0000-4000-8000-000000000011"}}
    snapshot = graph.get_state(graph_config)
    checkpoint_json = json.dumps(
        {
            "latest": snapshot.values,
            "history": [item.checkpoint for item in checkpointer.list(graph_config)],
        },
        default=str,
        ensure_ascii=True,
        sort_keys=True,
    )
    public_output_json = json.dumps(
        {
            "proposal": first.proposal.model_dump(mode="json"),
            "sections": first.sections.model_dump(mode="json"),
        },
        ensure_ascii=True,
        sort_keys=True,
    )

    private_values = (
        "Aarav Sharma",
        "aarav@example.com",
        "https://github.com/aarav",
        sample_resume_text.strip(),
        sample_job_text.strip(),
    )
    for private_value in private_values:
        assert private_value not in checkpoint_json
        assert private_value not in public_output_json

    captured_prompts = json.dumps(first_model.prompts, ensure_ascii=True)
    for contact_value in private_values[:3]:
        assert contact_value not in captured_prompts


def test_live_draft_start_restores_existing_interrupt_without_rerunning_model_nodes(
    settings,
    sample_resume_text,
    sample_job_text,
):
    first_runner, first_model = _runner(settings, sample_resume_text, sample_job_text)
    retry_runner, retry_model = _runner(settings, sample_resume_text, sample_job_text)
    checkpointer = InMemorySaver()
    operation_id = "00000000-0000-4000-8000-000000000013"

    first = first_runner.start(
        operation_id=operation_id,
        analysis_id=53,
        checkpointer=checkpointer,
    )
    restored = retry_runner.start(
        operation_id=operation_id,
        analysis_id=53,
        checkpointer=checkpointer,
    )

    assert first.paused is True
    assert restored.paused is True
    assert restored.proposal_revision == first.proposal_revision
    assert restored.proposal == first.proposal
    assert first_model.invoke_count == 3
    assert retry_model.invoke_count == 0


def test_live_draft_start_continues_incomplete_checkpoint_without_rerunning_completed_node(
    settings,
    sample_resume_text,
    sample_job_text,
):
    failing_runner, failing_model = _runner(
        settings,
        sample_resume_text,
        sample_job_text,
        fail_on_call=2,
    )
    retry_runner, retry_model = _runner(settings, sample_resume_text, sample_job_text)
    checkpointer = InMemorySaver()
    operation_id = "00000000-0000-4000-8000-000000000014"

    with pytest.raises(RuntimeError, match="simulated structured model interruption"):
        failing_runner.start(
            operation_id=operation_id,
            analysis_id=54,
            checkpointer=checkpointer,
        )
    restored = retry_runner.start(
        operation_id=operation_id,
        analysis_id=54,
        checkpointer=checkpointer,
    )

    assert restored.paused is True
    assert failing_model.invoke_count == 2
    assert retry_model.invoke_count == 2


def test_live_draft_graph_replaces_blocked_claims_before_interrupt(
    settings,
    sample_resume_text,
    sample_job_text,
):
    runner, _model = _runner(
        settings,
        sample_resume_text,
        sample_job_text,
        unsafe=True,
    )
    checkpointer = InMemorySaver()

    paused = runner.start(
        operation_id="00000000-0000-4000-8000-000000000021",
        analysis_id=61,
        checkpointer=checkpointer,
    )

    proposal_json = paused.proposal.model_dump_json()
    assert paused.paused is True
    assert set(paused.validation_warning_codes) >= {
        "live_resume_match_blocked",
        "live_cover_letter_blocked",
        "live_interview_coach_blocked",
    }
    for unsupported_text in ("Invented Corp", "1,000,000", "Imaginary Labs", "900%"):
        assert unsupported_text not in proposal_json

    graph_config = {"configurable": {"thread_id": "00000000-0000-4000-8000-000000000021"}}
    checkpoint_json = json.dumps(
        [item.checkpoint for item in checkpointer.list(graph_config)],
        default=str,
        ensure_ascii=True,
        sort_keys=True,
    )
    for private_value in (
        "Aarav Sharma",
        "aarav@example.com",
        "https://github.com/aarav",
        sample_resume_text.strip(),
        sample_job_text.strip(),
    ):
        assert private_value not in checkpoint_json
        assert private_value not in proposal_json


def test_live_draft_sanitizes_model_contact_data_and_applies_exact_approved_proposal(
    settings,
    sample_resume_text,
    sample_job_text,
):
    runner, _model = _runner(
        settings,
        sample_resume_text,
        sample_job_text,
        include_contact=True,
    )
    checkpointer = InMemorySaver()
    operation_id = "00000000-0000-4000-8000-000000000022"
    paused = runner.start(operation_id=operation_id, analysis_id=62, checkpointer=checkpointer)
    resumed = runner.resume(
        operation_id=operation_id,
        decision=WorkflowApprovalDecision.approve,
        proposal_revision=paused.proposal_revision,
        checkpointer=checkpointer,
    )

    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)
    match = match_resume_to_job(resume, job)
    deterministic = run_application_agent_workflow(
        analysis_id=1,
        resume=resume,
        job=job,
        match=match,
    )
    approved = apply_approved_live_draft(
        resume=resume,
        job=job,
        match=match,
        deterministic_result=deterministic,
        settings=settings,
        sections=resumed.sections,
        proposal=paused.proposal,
        live_duration_ms=resumed.duration_ms,
    )
    graph_config = {"configurable": {"thread_id": operation_id}}
    checkpoint_json = json.dumps(
        [item.checkpoint for item in checkpointer.list(graph_config)],
        default=str,
        ensure_ascii=True,
        sort_keys=True,
    )

    for private_value in (
        "Aarav Sharma",
        "aarav@example.com",
        "https://github.com/aarav",
        "+91 98765 43210",
    ):
        assert private_value not in checkpoint_json
        assert private_value not in paused.proposal.model_dump_json()
        assert private_value not in approved.report.model_dump_json()
    assert approved.report.executive_summary == paused.proposal.executive_summary
    assert approved.report.cover_letter == paused.proposal.cover_letter
    assert approved.report.interview_questions == paused.proposal.interview_questions


def test_live_draft_rejects_changed_score_and_invented_fit_skill(
    settings,
    sample_resume_text,
    sample_job_text,
):
    runner, _model = _runner(
        settings,
        sample_resume_text,
        sample_job_text,
        deceptive_fit=True,
    )
    paused = runner.start(
        operation_id="00000000-0000-4000-8000-000000000023",
        analysis_id=63,
        checkpointer=InMemorySaver(),
    )
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)
    match = match_resume_to_job(resume, job)
    deterministic = run_application_agent_workflow(
        analysis_id=1,
        resume=resume,
        job=job,
        match=match,
    )

    assert "live_resume_match_blocked" in paused.validation_warning_codes
    assert paused.proposal.executive_summary == deterministic.report.executive_summary.replace(
        resume.candidate.name or "", "Candidate"
    )
    assert "99/100" not in paused.proposal.executive_summary
    assert "Kubernetes" not in paused.proposal.executive_summary


def _runner(
    settings,
    resume_text: str,
    job_text: str,
    *,
    unsafe: bool = False,
    include_contact: bool = False,
    deceptive_fit: bool = False,
    fail_on_call: int | None = None,
):
    resume = parse_resume_profile(resume_text, resume_id=1)
    job = parse_job_profile(job_text, job_id=1)
    match = match_resume_to_job(resume, job)
    deterministic = run_application_agent_workflow(
        analysis_id=1,
        resume=resume,
        job=job,
        match=match,
    )
    model = _FakeStructuredModel(
        match,
        unsafe=unsafe,
        include_contact=include_contact,
        deceptive_fit=deceptive_fit,
        fail_on_call=fail_on_call,
    )
    settings.vertex_project_id = "resumepilot-test-project"
    runner = LiveDraftGraphRunner(
        settings=settings,
        resume=resume,
        job=job,
        match=match,
        deterministic_report=deterministic.report,
        model_factory=lambda _settings: model,
    )
    return runner, model


class _FakeStructuredModel:
    def __init__(
        self,
        match,
        *,
        unsafe: bool,
        include_contact: bool,
        deceptive_fit: bool,
        fail_on_call: int | None,
    ) -> None:
        self.match = match
        self.unsafe = unsafe
        self.include_contact = include_contact
        self.deceptive_fit = deceptive_fit
        self.fail_on_call = fail_on_call
        self.invoke_count = 0
        self.prompts = []

    def with_structured_output(self, schema, **_kwargs):
        model = self

        class Runnable:
            def invoke(self, prompt):
                model.invoke_count += 1
                model.prompts.append(prompt)
                if model.invoke_count == model.fail_on_call:
                    raise RuntimeError("simulated structured model interruption")
                return {
                    "parsed": model._output(schema),
                    "raw": SimpleNamespace(
                        usage_metadata={
                            "total_tokens": 30,
                            "input_tokens": 20,
                            "output_tokens": 10,
                        }
                    ),
                }

        return Runnable()

    def _output(self, schema):
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for item in self.match.matched_skills
                for evidence_id in item.resume_evidence_ids
            )
        )[:3]
        assert evidence_ids
        if schema is ResumeMatchAgentOutput:
            return ResumeMatchAgentOutput(
                summary=(
                    "Senior executive at Invented Corp who served 1,000,000 users."
                    if self.unsafe
                    else (
                        "The fit score is 99/100 because the candidate is a Kubernetes expert."
                        if self.deceptive_fit
                        else (
                            "Aarav Sharma at aarav@example.com is supported by linked "
                            "resume evidence."
                            if self.include_contact
                            else "The deterministic match is supported by linked resume evidence."
                        )
                    )
                ),
                strongest_matches=[],
                weak_areas=[],
                recommended_positioning=(
                    "Lead with the certified production record."
                    if self.unsafe
                    else "Use linked evidence and describe gaps honestly."
                ),
                evidence_ids=evidence_ids,
                confidence=self.match.confidence,
            )
        if schema is CoverLetterAgentOutput:
            draft = (
                "I worked at Imaginary Labs and drove 900% revenue growth."
                if self.unsafe
                else (
                    "Dear Hiring Team,\n\n"
                    + (
                        "Contact Aarav Sharma at aarav@example.com, +91 98765 43210, or "
                        "https://github.com/aarav. "
                        if self.include_contact
                        else ""
                    )
                    + "The linked resume evidence supports this application.\n\n"
                    "Confidence note: review the evidence before use."
                )
            )
            return CoverLetterAgentOutput(
                draft=draft,
                confidence_note="Confidence note: review the evidence before use.",
                evidence_ids=evidence_ids,
            )
        if schema is InterviewCoachAgentOutput:
            return InterviewCoachAgentOutput(
                question_groups=[
                    InterviewQuestionGroup(
                        category="Technical",
                        questions=["Which evidence best demonstrates the relevant work?"],
                        suggested_answer_evidence_ids=(
                            ["invented_001"] if self.unsafe else evidence_ids
                        ),
                    )
                ]
            )
        raise AssertionError(f"Unexpected structured schema: {schema}")
