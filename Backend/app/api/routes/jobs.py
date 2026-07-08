from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings
from app.core.config import Settings
from app.schemas.job import JobAnalysisRequest, JobAnalysisResponse
from app.services.analysis_service import analyze_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/analyze", response_model=JobAnalysisResponse)
def analyze_job_description(
    request: JobAnalysisRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JobAnalysisResponse:
    return analyze_job(db, request, settings)
