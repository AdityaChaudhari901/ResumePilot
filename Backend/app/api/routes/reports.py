from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings
from app.core.config import Settings
from app.schemas.agent import ReportWorkflowTraceResponse
from app.schemas.auth import CurrentUser
from app.schemas.privacy import ReportDeleteResponse
from app.schemas.report import ApplicationReport, ReportHistoryResponse
from app.services.analysis_service import (
    ensure_report_access,
    get_report,
    get_report_markdown,
    get_report_trace,
    get_tailored_resume_docx,
    get_tailored_resume_latex,
    get_tailored_resume_pdf,
    list_report_history,
)
from app.services.application_service import mark_application_exported_for_report
from app.services.audit_service import record_audit_event
from app.services.privacy_service import delete_report
from app.services.usage_service import enforce_export_limit, record_export_usage

router = APIRouter(prefix="/reports", tags=["reports"])
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("", response_model=ReportHistoryResponse)
def list_reports(
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReportHistoryResponse:
    return list_report_history(db, current_user, limit=limit)


@router.get("/{report_id}", response_model=ApplicationReport)
def read_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApplicationReport:
    return get_report(db, report_id, current_user)


@router.get("/{report_id}/markdown", response_class=PlainTextResponse)
def read_report_markdown(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> str:
    ensure_report_access(db, report_id, current_user)
    enforce_export_limit(db, current_user)
    markdown = get_report_markdown(db, report_id, current_user)
    record_audit_event(
        db,
        event_type="report.exported",
        user_id=current_user.id,
        payload={"report_id": report_id, "format": "markdown"},
    )
    record_export_usage(db, current_user, report_id=report_id, export_format="markdown")
    mark_application_exported_for_report(db, current_user, report_id=report_id)
    return markdown


@router.get("/{report_id}/trace", response_model=ReportWorkflowTraceResponse)
def read_report_trace(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReportWorkflowTraceResponse:
    return get_report_trace(db, report_id, current_user)


@router.get("/{report_id}/resume/latex", response_class=PlainTextResponse)
def read_tailored_resume_latex(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PlainTextResponse:
    ensure_report_access(db, report_id, current_user)
    enforce_export_limit(db, current_user)
    latex = get_tailored_resume_latex(db, report_id, current_user)
    record_audit_event(
        db,
        event_type="report.exported",
        user_id=current_user.id,
        payload={"report_id": report_id, "format": "latex"},
    )
    record_export_usage(db, current_user, report_id=report_id, export_format="latex")
    mark_application_exported_for_report(db, current_user, report_id=report_id)
    return PlainTextResponse(
        content=latex,
        media_type="application/x-tex",
        headers={
            "Content-Disposition": f'attachment; filename="resumepilot-report-{report_id}.tex"'
        },
    )


@router.get("/{report_id}/resume/docx")
def read_tailored_resume_docx(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    ensure_report_access(db, report_id, current_user)
    enforce_export_limit(db, current_user)
    docx = get_tailored_resume_docx(db, report_id, current_user)
    record_audit_event(
        db,
        event_type="report.exported",
        user_id=current_user.id,
        payload={"report_id": report_id, "format": "docx"},
    )
    record_export_usage(db, current_user, report_id=report_id, export_format="docx")
    mark_application_exported_for_report(db, current_user, report_id=report_id)
    return Response(
        content=docx,
        media_type=DOCX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="resumepilot-report-{report_id}.docx"'
        },
    )


@router.get("/{report_id}/resume/pdf")
def read_tailored_resume_pdf(
    report_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    ensure_report_access(db, report_id, current_user)
    enforce_export_limit(db, current_user)
    pdf = get_tailored_resume_pdf(db, report_id, settings, current_user)
    record_audit_event(
        db,
        event_type="report.exported",
        user_id=current_user.id,
        payload={"report_id": report_id, "format": "pdf"},
    )
    record_export_usage(db, current_user, report_id=report_id, export_format="pdf")
    mark_application_exported_for_report(db, current_user, report_id=report_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="resumepilot-report-{report_id}.pdf"'
        },
    )


@router.delete("/{report_id}", response_model=ReportDeleteResponse)
def delete_report_data(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReportDeleteResponse:
    return delete_report(db, report_id, current_user)
