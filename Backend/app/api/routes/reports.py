from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings
from app.core.config import Settings
from app.schemas.agent import ReportWorkflowTraceResponse
from app.schemas.privacy import ReportDeleteResponse
from app.schemas.report import ApplicationReport
from app.services.analysis_service import (
    get_report,
    get_report_markdown,
    get_report_trace,
    get_tailored_resume_docx,
    get_tailored_resume_latex,
    get_tailored_resume_pdf,
)
from app.services.audit_service import record_audit_event
from app.services.privacy_service import delete_report

router = APIRouter(prefix="/reports", tags=["reports"])
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("/{report_id}", response_model=ApplicationReport)
def read_report(report_id: int, db: Session = Depends(get_db)) -> ApplicationReport:
    return get_report(db, report_id)


@router.get("/{report_id}/markdown", response_class=PlainTextResponse)
def read_report_markdown(report_id: int, db: Session = Depends(get_db)) -> str:
    markdown = get_report_markdown(db, report_id)
    record_audit_event(
        db,
        event_type="report.exported",
        payload={"report_id": report_id, "format": "markdown"},
    )
    return markdown


@router.get("/{report_id}/trace", response_model=ReportWorkflowTraceResponse)
def read_report_trace(report_id: int, db: Session = Depends(get_db)) -> ReportWorkflowTraceResponse:
    return get_report_trace(db, report_id)


@router.get("/{report_id}/resume/latex", response_class=PlainTextResponse)
def read_tailored_resume_latex(report_id: int, db: Session = Depends(get_db)) -> PlainTextResponse:
    latex = get_tailored_resume_latex(db, report_id)
    record_audit_event(
        db,
        event_type="report.exported",
        payload={"report_id": report_id, "format": "latex"},
    )
    return PlainTextResponse(
        content=latex,
        media_type="application/x-tex",
        headers={
            "Content-Disposition": f'attachment; filename="resumepilot-report-{report_id}.tex"'
        },
    )


@router.get("/{report_id}/resume/docx")
def read_tailored_resume_docx(report_id: int, db: Session = Depends(get_db)) -> Response:
    docx = get_tailored_resume_docx(db, report_id)
    record_audit_event(
        db,
        event_type="report.exported",
        payload={"report_id": report_id, "format": "docx"},
    )
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
) -> Response:
    pdf = get_tailored_resume_pdf(db, report_id, settings)
    record_audit_event(
        db,
        event_type="report.exported",
        payload={"report_id": report_id, "format": "pdf"},
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="resumepilot-report-{report_id}.pdf"'
        },
    )


@router.delete("/{report_id}", response_model=ReportDeleteResponse)
def delete_report_data(report_id: int, db: Session = Depends(get_db)) -> ReportDeleteResponse:
    return delete_report(db, report_id)
