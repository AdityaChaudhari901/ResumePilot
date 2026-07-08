from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.report import ApplicationReport
from app.services.analysis_service import get_report, get_report_markdown

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{report_id}", response_model=ApplicationReport)
def read_report(report_id: int, db: Session = Depends(get_db)) -> ApplicationReport:
    return get_report(db, report_id)


@router.get("/{report_id}/markdown", response_class=PlainTextResponse)
def read_report_markdown(report_id: int, db: Session = Depends(get_db)) -> str:
    return get_report_markdown(db, report_id)
