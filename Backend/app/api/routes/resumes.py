from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings
from app.core.config import Settings
from app.schemas.auth import CurrentUser
from app.schemas.privacy import ResumeDeleteResponse
from app.schemas.resume import ResumeProfile, ResumeUploadResponse
from app.services.analysis_service import create_resume_from_upload
from app.services.file_storage import store_resume_upload
from app.services.privacy_service import delete_resume

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/upload", response_model=ResumeUploadResponse, status_code=201)
async def upload_resume(
    file: UploadFile,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: CurrentUser = Depends(get_current_user),
) -> ResumeUploadResponse:
    upload = await store_resume_upload(file, settings, owner_namespace=str(current_user.id))
    record = create_resume_from_upload(db, upload, current_user)
    profile = ResumeProfile.model_validate(record.profile_json)
    return ResumeUploadResponse(
        resume_id=record.id,
        candidate_name=profile.candidate.name,
        status="parsed",
        warnings=profile.warnings,
    )


@router.delete("/{resume_id}", response_model=ResumeDeleteResponse)
def delete_resume_data(
    resume_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: CurrentUser = Depends(get_current_user),
) -> ResumeDeleteResponse:
    return delete_resume(db, resume_id, settings, current_user)
