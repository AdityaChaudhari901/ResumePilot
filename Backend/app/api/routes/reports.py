from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings
from app.core.config import Settings
from app.db.models import ApplicationRecord
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
from app.services.audit_service import add_audit_event
from app.services.privacy_service import delete_report
from app.services.usage_service import reserve_export_usage

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


@router.post("/{report_id}/markdown", response_class=PlainTextResponse)
def read_report_markdown(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> str:
    ensure_report_access(db, report_id, current_user)
    markdown = get_report_markdown(db, report_id, current_user)
    _finalize_report_export(db, current_user, report_id, "markdown")
    return PlainTextResponse(
        content=markdown,
        media_type="text/plain",
        headers=_download_headers(f"resumepilot-report-{report_id}.md"),
    )


@router.get("/{report_id}/trace", response_model=ReportWorkflowTraceResponse)
def read_report_trace(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReportWorkflowTraceResponse:
    return get_report_trace(db, report_id, current_user)


@router.post("/{report_id}/resume/latex", response_class=PlainTextResponse)
def read_tailored_resume_latex(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PlainTextResponse:
    ensure_report_access(db, report_id, current_user)
    latex = get_tailored_resume_latex(db, report_id, current_user)
    _finalize_report_export(db, current_user, report_id, "latex")
    return PlainTextResponse(
        content=latex,
        media_type="application/x-tex",
        headers=_download_headers(f"resumepilot-report-{report_id}.tex"),
    )


@router.post("/{report_id}/resume/docx")
def read_tailored_resume_docx(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    ensure_report_access(db, report_id, current_user)
    docx = get_tailored_resume_docx(db, report_id, current_user)
    _finalize_report_export(db, current_user, report_id, "docx")
    return Response(
        content=docx,
        media_type=DOCX_MEDIA_TYPE,
        headers=_download_headers(f"resumepilot-report-{report_id}.docx"),
    )


@router.post("/{report_id}/resume/pdf")
def read_tailored_resume_pdf(
    report_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    ensure_report_access(db, report_id, current_user)
    pdf = get_tailored_resume_pdf(db, report_id, settings, current_user)
    _finalize_report_export(db, current_user, report_id, "pdf")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers=_download_headers(f"resumepilot-report-{report_id}.pdf"),
    )


def _finalize_report_export(
    db: Session,
    current_user: CurrentUser,
    report_id: int,
    export_format: str,
) -> None:
    application = db.scalar(
        select(ApplicationRecord)
        .where(
            ApplicationRecord.report_id == report_id,
            ApplicationRecord.user_id == current_user.id,
        )
        .with_for_update()
    )
    reserve_export_usage(db, current_user, report_id=report_id, export_format=export_format)
    add_audit_event(
        db,
        event_type="report.exported",
        user_id=current_user.id,
        payload={"report_id": report_id, "format": export_format},
    )
    if application and application.status != "applied":
        application.status = "exported"
        db.add(application)
    db.commit()


def _download_headers(filename: str) -> dict[str, str]:
    return {
        "Cache-Control": "private, no-store",
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Content-Type-Options": "nosniff",
    }


@router.delete("/{report_id}", response_model=ReportDeleteResponse)
def delete_report_data(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReportDeleteResponse:
    return delete_report(db, report_id, current_user)
