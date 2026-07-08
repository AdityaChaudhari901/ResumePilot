from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.job import JobAnalysisRequest, JobAnalysisResponse
from app.services.analysis_service import analyze_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/analyze", response_model=JobAnalysisResponse)
def analyze_job_description(
    request: JobAnalysisRequest,
    db: Session = Depends(get_db),
) -> JobAnalysisResponse:
    return analyze_job(db, request)
