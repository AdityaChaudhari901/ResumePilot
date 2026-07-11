from datetime import UTC, datetime

import pytest
from fastapi import HTTPException, status
from sqlalchemy import select

from app.db.models import AnalysisRecord, UsageEventRecord, UserRecord, WorkflowJobRecord
from app.schemas.agent import (
    AgentStepName,
    AgentTokenUsage,
    AgentWorkflowMode,
    AgentWorkflowResult,
    AgentWorkflowTrace,
    CoverLetterAgentOutput,
    InterviewCoachAgentOutput,
    LiveDraftSections,
    ResumeMatchAgentOutput,
)
from app.schemas.operation import LiveDraftProposal
from app.schemas.report import ApplicationReport, InterviewQuestionGroup
from app.services.langgraph_workflow import LiveDraftGraphResult
from app.services.workflow_job_service import _persist_agent_result
from tests.api_helpers import submit_analysis

USER_A_HEADERS = {
    "X-ResumePilot-User": "approval-user-a",
    "X-ResumePilot-Email": "approval-a@example.com",
    "X-ResumePilot-Name": "Approval User A",
}
USER_B_HEADERS = {
    "X-ResumePilot-User": "approval-user-b",
    "X-ResumePilot-Email": "approval-b@example.com",
    "X-ResumePilot-Name": "Approval User B",
}


def test_live_analysis_waits_for_approval_and_releases_worker_lease(
    client,
    monkeypatch,
    settings,
    sample_resume_text,
    sample_job_text,
):
    calls = _install_fake_graph_runner(monkeypatch)
    operation = _start_live_analysis(
        client,
        settings,
        sample_resume_text,
        sample_job_text,
        idempotency_key="langgraph-waiting-lease",
    )

    assert operation["status"] == "waiting_for_approval"
    assert isinstance(operation["application_id"], int)
    assert operation["stage"] == "approval_required"
    assert operation["progress_percent"] == 90
    assert operation["cancelable"] is True
    assert operation["finished_at"] is None
    assert operation["approval"]["status"] == "pending"
    assert operation["approval"]["id"] == "a" * 64
    assert operation["result"]["scoring_version"] == "evidence_v2"
    assert operation["result"]["score_status"] == "scored"
    assert "_approval" not in (operation["result"] or {})
    assert calls == {"start": 1, "resume": 0}

    application_id = operation["application_id"]
    applications = client.get("/applications").json()["items"]
    assert [application["id"] for application in applications] == [application_id]
    active = client.get(
        "/operations/active",
        params={"kind": "analysis", "application_id": application_id},
    )
    assert active.status_code == 200
    assert [item["id"] for item in active.json()["items"]] == [operation["id"]]
    assert client.get(f"/operations/{operation['id']}").json()["application_id"] == application_id

    with client.app.state.session_factory() as db:
        record = db.get(WorkflowJobRecord, operation["id"])
        assert record is not None
        assert record.status == "waiting_for_approval"
        assert record.analysis_id == operation["result"]["analysis_id"]
        assert record.lease_owner is None
        assert record.lease_expires_at is None
        assert record.heartbeat_at is None


def test_live_ai_limit_returns_successful_deterministic_baseline(
    client,
    monkeypatch,
    settings,
    sample_resume_text,
    sample_job_text,
):
    calls = _install_fake_graph_runner(monkeypatch)
    settings.agent_workflow_mode = AgentWorkflowMode.langgraph
    settings.vertex_project_id = "resumepilot-test-project"
    upload = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", sample_resume_text.encode(), "text/markdown")},
    )
    assert upload.status_code == 201
    _set_plan(client, "local-dev-user", "premium")

    def raise_live_limit(*_args, **_kwargs):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "plan_limit_reached"},
        )

    monkeypatch.setattr(
        "app.services.workflow_job_service.reserve_live_ai_usage",
        raise_live_limit,
    )
    response, operation = submit_analysis(
        client,
        {
            "resume_id": upload.json()["resume_id"],
            "job_text": sample_job_text,
            "allow_live_ai_processing": True,
        },
        idempotency_key="langgraph-live-limit-baseline",
    )

    assert response.status_code == 202
    assert operation is not None
    assert operation["status"] == "succeeded"
    assert operation["result"]["report_id"]
    assert calls == {"start": 0, "resume": 0}
    trace = client.get(f"/reports/{operation['result']['report_id']}/trace").json()["trace"]
    assert "live_ai_limit_reached" in trace["validation_warning_codes"]
    assert trace["runtime_metadata"]["runtime_status"] == "skipped_limit"
    assert _usage_limit(client, "analyses")["used"] == 1
    assert _usage_limit(client, "live_ai_runs")["used"] == 0


def test_approval_is_tenant_scoped_idempotent_and_rejects_conflicting_decision(
    client,
    monkeypatch,
    settings,
    sample_resume_text,
    sample_job_text,
):
    _install_fake_graph_runner(monkeypatch)
    operation = _start_live_analysis(
        client,
        settings,
        sample_resume_text,
        sample_job_text,
        headers=USER_A_HEADERS,
        external_id="approval-user-a",
        idempotency_key="langgraph-tenant-approval",
    )
    approval_id = operation["approval"]["id"]
    payload = {"approval_id": approval_id, "decision": "approve"}

    cross_tenant = client.post(
        f"/operations/{operation['id']}/approval",
        json=payload,
        headers={**USER_B_HEADERS, "Idempotency-Key": "cross-tenant-approval"},
    )
    assert cross_tenant.status_code == 404

    first = client.post(
        f"/operations/{operation['id']}/approval",
        json=payload,
        headers={**USER_A_HEADERS, "Idempotency-Key": "approve-live-draft-once"},
    )
    replay = client.post(
        f"/operations/{operation['id']}/approval",
        json=payload,
        headers={**USER_A_HEADERS, "Idempotency-Key": "approve-live-draft-once"},
    )

    assert first.status_code == 202
    assert replay.status_code == 202
    assert first.json()["id"] == replay.json()["id"] == operation["id"]
    assert first.json()["status"] == replay.json()["status"] == "succeeded"
    assert first.json()["approval"]["status"] == "approved"
    assert replay.json()["approval"]["decision"] == "approve"

    conflicting = client.post(
        f"/operations/{operation['id']}/approval",
        json={"approval_id": approval_id, "decision": "reject"},
        headers={**USER_A_HEADERS, "Idempotency-Key": "conflicting-live-draft"},
    )
    assert conflicting.status_code == 409
    assert conflicting.json()["detail"]["code"] == "approval_already_decided"


def test_canceling_waiting_approval_is_immediate_and_does_not_refund_live_work(
    client,
    monkeypatch,
    settings,
    sample_resume_text,
    sample_job_text,
):
    _install_fake_graph_runner(monkeypatch)
    operation = _start_live_analysis(
        client,
        settings,
        sample_resume_text,
        sample_job_text,
        idempotency_key="langgraph-cancel-waiting",
    )

    canceled = client.post(f"/operations/{operation['id']}/cancel")

    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"
    assert canceled.json()["progress_percent"] == 100
    assert canceled.json()["cancelable"] is False
    assert _usage_limit(client, "live_ai_runs")["used"] == 1
    with client.app.state.session_factory() as db:
        record = db.get(WorkflowJobRecord, operation["id"])
        assert record is not None
        assert record.lease_owner is None
        assert record.lease_expires_at is None


def test_canceling_submitted_approval_deletes_checkpoint_before_worker_claim(
    client,
    monkeypatch,
    settings,
    sample_resume_text,
    sample_job_text,
):
    _install_fake_graph_runner(monkeypatch)
    deleted_threads: list[str] = []
    monkeypatch.setattr(
        "app.services.workflow_job_service.delete_workflow_checkpoint",
        lambda _settings, thread_id: deleted_threads.append(thread_id),
    )
    operation = _start_live_analysis(
        client,
        settings,
        sample_resume_text,
        sample_job_text,
        idempotency_key="langgraph-cancel-submitted",
    )
    settings.workflow_inline_execution = False

    submitted = _submit_decision(
        client,
        operation,
        "approve",
        "submit-then-cancel-live-draft",
    )
    canceled = client.post(f"/operations/{operation['id']}/cancel")

    assert submitted.status_code == 202
    assert submitted.json()["status"] == "queued"
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"
    assert deleted_threads == [operation["id"]]


def test_approved_live_proposal_updates_report_and_consumes_live_usage_once(
    client,
    monkeypatch,
    settings,
    sample_resume_text,
    sample_job_text,
):
    calls = _install_fake_graph_runner(monkeypatch)
    operation = _start_live_analysis(
        client,
        settings,
        sample_resume_text,
        sample_job_text,
        idempotency_key="langgraph-approve-report",
    )
    report_id = operation["result"]["report_id"]
    baseline = client.get(f"/reports/{report_id}").json()

    approved = _submit_decision(client, operation, "approve", "approve-report-once")
    final_report = client.get(f"/reports/{report_id}").json()
    trace = client.get(f"/reports/{report_id}/trace").json()["trace"]

    assert approved.status_code == 202
    assert approved.json()["status"] == "succeeded"
    assert approved.json()["approval"]["status"] == "approved"
    assert final_report["executive_summary"] != baseline["executive_summary"]
    assert final_report["executive_summary"].startswith(
        "The deterministic match is supported by linked resume evidence."
    )
    assert final_report["cover_letter"].startswith("Dear Hiring Team")
    assert final_report["match_score"] == baseline["match_score"]
    assert final_report["scoring_version"] == baseline["scoring_version"] == "evidence_v2"
    assert final_report["score_status"] == baseline["score_status"]
    assert final_report["score_breakdown"] == baseline["score_breakdown"]
    assert trace["mode"] == "langgraph"
    assert trace["steps"][-1]["name"] == "human_approval"
    assert _usage_limit(client, "live_ai_runs") == {
        "used": 1,
        "limit": 100,
        "remaining": 99,
    }
    assert calls == {"start": 1, "resume": 1}

    replay = _submit_decision(client, operation, "approve", "approve-report-once")
    assert replay.status_code == 202
    assert _usage_limit(client, "live_ai_runs")["used"] == 1
    assert calls == {"start": 1, "resume": 1}


def test_live_result_persistence_rejects_score_contract_tampering(
    client,
    monkeypatch,
    settings,
    sample_resume_text,
    sample_job_text,
):
    _install_fake_graph_runner(monkeypatch)
    operation = _start_live_analysis(
        client,
        settings,
        sample_resume_text,
        sample_job_text,
        idempotency_key="langgraph-score-contract-tamper",
    )
    baseline_payload = client.get(f"/reports/{operation['result']['report_id']}").json()

    with client.app.state.session_factory() as db:
        analysis = db.get(AnalysisRecord, operation["result"]["analysis_id"])
        assert analysis is not None
        original_report_json = dict(analysis.report_json)
        tampered_report = ApplicationReport.model_validate(baseline_payload).model_copy(
            update={"match_score": baseline_payload["match_score"] + 1}
        )
        tampered_result = AgentWorkflowResult(
            report=tampered_report,
            trace=AgentWorkflowTrace.model_validate(analysis.workflow_trace_json),
        )

        with pytest.raises(RuntimeError, match="Analysis and report match scores"):
            _persist_agent_result(db, analysis, tampered_result)
        assert analysis.report_json == original_report_json


def test_rejected_live_proposal_keeps_deterministic_report(
    client,
    monkeypatch,
    settings,
    sample_resume_text,
    sample_job_text,
):
    _install_fake_graph_runner(monkeypatch)
    operation = _start_live_analysis(
        client,
        settings,
        sample_resume_text,
        sample_job_text,
        idempotency_key="langgraph-reject-report",
    )
    report_id = operation["result"]["report_id"]
    baseline = client.get(f"/reports/{report_id}").json()

    rejected = _submit_decision(client, operation, "reject", "reject-report-once")
    final_report = client.get(f"/reports/{report_id}").json()
    trace = client.get(f"/reports/{report_id}/trace").json()["trace"]

    assert rejected.status_code == 202
    assert rejected.json()["status"] == "succeeded"
    assert rejected.json()["approval"]["status"] == "rejected"
    assert final_report == baseline
    assert trace["mode"] == "deterministic_fallback"
    assert trace["steps"][0]["name"] == "langgraph_runtime"
    assert trace["steps"][1]["name"] == "human_approval"
    assert trace["runtime_metadata"]["runtime_status"] == "rejected"
    assert _usage_limit(client, "live_ai_runs")["used"] == 1


def test_report_deletion_scrubs_live_ai_usage_correlation(
    client,
    monkeypatch,
    settings,
    sample_resume_text,
    sample_job_text,
):
    _install_fake_graph_runner(monkeypatch)
    operation = _start_live_analysis(
        client,
        settings,
        sample_resume_text,
        sample_job_text,
        idempotency_key="langgraph-live-usage-privacy",
    )
    approved = _submit_decision(client, operation, "approve", "approve-before-privacy-delete")
    assert approved.status_code == 202
    report_id = operation["result"]["report_id"]

    deleted = client.delete(f"/reports/{report_id}")

    assert deleted.status_code == 200
    with client.app.state.session_factory() as db:
        live_usage = db.scalar(
            select(UsageEventRecord).where(UsageEventRecord.event_type == "live_ai_run").limit(1)
        )
        assert live_usage is not None
        assert live_usage.state == "consumed"
        assert live_usage.reservation_key is None
        assert live_usage.metadata_json == {
            "status": "privacy_deleted",
            "previous_state": "consumed",
        }
        assert str(report_id) not in str(live_usage.metadata_json)
        assert operation["id"] not in str(live_usage.metadata_json)


def _start_live_analysis(
    client,
    settings,
    resume_text: str,
    job_text: str,
    *,
    idempotency_key: str,
    headers: dict[str, str] | None = None,
    external_id: str = "local-dev-user",
) -> dict:
    settings.agent_workflow_mode = AgentWorkflowMode.langgraph
    settings.vertex_project_id = "resumepilot-test-project"
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", resume_text.encode("utf-8"), "text/markdown")},
        headers=headers,
    )
    assert upload_response.status_code == 201
    _set_plan(client, external_id, "premium")
    response, operation = submit_analysis(
        client,
        {
            "resume_id": upload_response.json()["resume_id"],
            "job_text": job_text,
            "allow_live_ai_processing": True,
        },
        headers=headers,
        idempotency_key=idempotency_key,
    )
    assert response.status_code == 202
    assert operation is not None
    assert operation["status"] == "waiting_for_approval", operation
    return operation


def _submit_decision(client, operation: dict, decision: str, idempotency_key: str):
    return client.post(
        f"/operations/{operation['id']}/approval",
        json={"approval_id": operation["approval"]["id"], "decision": decision},
        headers={"Idempotency-Key": idempotency_key},
    )


def _set_plan(client, external_id: str, plan: str) -> None:
    with client.app.state.session_factory() as db:
        user = db.scalar(select(UserRecord).where(UserRecord.external_id == external_id).limit(1))
        assert user is not None
        user.plan = plan
        user.subscription_status = "active"
        db.commit()


def _usage_limit(client, metric: str) -> dict[str, int | None]:
    summary = client.get("/usage/summary").json()
    item = next(item for item in summary["limits"] if item["metric"] == metric)
    return {"used": item["used"], "limit": item["limit"], "remaining": item["remaining"]}


def _install_fake_graph_runner(monkeypatch) -> dict[str, int]:
    calls = {"start": 0, "resume": 0}

    class FakeLiveDraftGraphRunner:
        def __init__(self, *, match, **_kwargs):
            self.match = match
            self.sections = _safe_sections(match)

        def start(self, **_kwargs):
            calls["start"] += 1
            return _graph_result(self.sections, paused=True)

        def resume(self, *, decision, proposal_revision, **_kwargs):
            calls["resume"] += 1
            assert proposal_revision == "a" * 64
            return _graph_result(
                self.sections,
                paused=False,
                approval_decision=decision,
            )

    monkeypatch.setattr(
        "app.services.workflow_job_service.LiveDraftGraphRunner",
        FakeLiveDraftGraphRunner,
    )
    return calls


def _graph_result(sections, *, paused: bool, approval_decision=None):
    proposal = LiveDraftProposal(
        executive_summary=(
            "The deterministic match is supported by linked resume evidence. "
            "Recommended positioning: Use linked evidence and describe gaps honestly."
        ),
        cover_letter=sections.cover_letter.draft,
        interview_questions=sections.interview_coach.question_groups,
    )
    return LiveDraftGraphResult(
        paused=paused,
        sections=sections,
        proposal=proposal,
        proposal_revision="a" * 64,
        validation_warning_codes=[],
        requested_at=datetime.now(UTC),
        approval_decision=approval_decision,
        duration_ms=60,
    )


def _safe_sections(match) -> LiveDraftSections:
    evidence_ids = list(
        dict.fromkeys(
            evidence_id for item in match.matched_skills for evidence_id in item.resume_evidence_ids
        )
    )[:3]
    assert evidence_ids
    return LiveDraftSections(
        resume_match=ResumeMatchAgentOutput(
            summary="The deterministic match is supported by linked resume evidence.",
            strongest_matches=[],
            weak_areas=[],
            recommended_positioning="Use linked evidence and describe gaps honestly.",
            evidence_ids=evidence_ids,
            confidence=match.confidence,
        ),
        cover_letter=CoverLetterAgentOutput(
            draft=(
                "Dear Hiring Team,\n\nThe linked resume evidence supports this application.\n\n"
                "Confidence note: review the validated evidence before use."
            ),
            confidence_note="Confidence note: review the validated evidence before use.",
            evidence_ids=evidence_ids,
        ),
        interview_coach=InterviewCoachAgentOutput(
            question_groups=[
                InterviewQuestionGroup(
                    category="Technical",
                    questions=["Which linked evidence best demonstrates the relevant work?"],
                    suggested_answer_evidence_ids=evidence_ids,
                )
            ]
        ),
        step_durations_ms={
            AgentStepName.resume_match.value: 10,
            AgentStepName.cover_letter.value: 20,
            AgentStepName.interview_coach.value: 30,
        },
        token_usage=AgentTokenUsage(
            total_tokens=123,
            prompt_tokens=90,
            completion_tokens=33,
            successful_requests=3,
        ),
    )
