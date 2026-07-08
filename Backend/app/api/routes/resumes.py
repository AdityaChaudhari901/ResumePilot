from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings
from app.core.config import Settings
from app.schemas.resume import ResumeProfile, ResumeUploadResponse
from app.services.analysis_service import create_resume_from_upload
from app.services.file_storage import store_resume_upload

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/upload", response_model=ResumeUploadResponse, status_code=201)
async def upload_resume(
    file: UploadFile,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ResumeUploadResponse:
    upload = await store_resume_upload(file, settings)
    record = create_resume_from_upload(db, upload)
    profile = ResumeProfile.model_validate(record.profile_json)
    return ResumeUploadResponse(
        resume_id=record.id,
        candidate_name=profile.candidate.name,
        status="parsed",
        warnings=profile.warnings,
    )
