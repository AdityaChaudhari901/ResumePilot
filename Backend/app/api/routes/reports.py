from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.agent import ReportWorkflowTraceResponse
from app.schemas.report import ApplicationReport
from app.services.analysis_service import (
    get_report,
    get_report_markdown,
    get_report_trace,
    get_tailored_resume_latex,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{report_id}", response_model=ApplicationReport)
def read_report(report_id: int, db: Session = Depends(get_db)) -> ApplicationReport:
    return get_report(db, report_id)


@router.get("/{report_id}/markdown", response_class=PlainTextResponse)
def read_report_markdown(report_id: int, db: Session = Depends(get_db)) -> str:
    return get_report_markdown(db, report_id)


@router.get("/{report_id}/trace", response_model=ReportWorkflowTraceResponse)
def read_report_trace(report_id: int, db: Session = Depends(get_db)) -> ReportWorkflowTraceResponse:
    return get_report_trace(db, report_id)


@router.get("/{report_id}/resume/latex", response_class=PlainTextResponse)
def read_tailored_resume_latex(report_id: int, db: Session = Depends(get_db)) -> PlainTextResponse:
    latex = get_tailored_resume_latex(db, report_id)
    return PlainTextResponse(
        content=latex,
        media_type="application/x-tex",
        headers={
            "Content-Disposition": f'attachment; filename="resumepilot-report-{report_id}.tex"'
        },
    )
