from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings, require_allowed_sender, require_openclaw_auth
from app.core.config import Settings
from app.schemas.chat import OpenClawCommandRequest, OpenClawCommandResponse
from app.schemas.job import JobAnalysisRequest
from app.services.analysis_service import analyze_job, get_report_markdown, latest_resume

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/openclaw",
    response_model=OpenClawCommandResponse,
    dependencies=[Depends(require_openclaw_auth)],
)
def openclaw_command(
    request: OpenClawCommandRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OpenClawCommandResponse:
    require_allowed_sender(request.sender, settings)
    if request.command.lower() != "job":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported command")

    resume = latest_resume(db)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No resume has been uploaded"
        )

    analysis_request = _analysis_request_from_args(resume.id, request.args)
    response = analyze_job(db, analysis_request, settings)
    markdown = get_report_markdown(db, response.report_id)
    return OpenClawCommandResponse(
        status=response.status,
        message="Job analysis completed",
        analysis_id=response.analysis_id,
        report_id=response.report_id,
        markdown=markdown,
    )


def _analysis_request_from_args(resume_id: int, args: str) -> JobAnalysisRequest:
    cleaned = args.strip()
    if cleaned.startswith("paste:"):
        return JobAnalysisRequest(
            resume_id=resume_id, job_text=cleaned.removeprefix("paste:").strip()
        )
    if cleaned.startswith(("http://", "https://")):
        return JobAnalysisRequest(resume_id=resume_id, job_url=cleaned)
    return JobAnalysisRequest(resume_id=resume_id, job_text=cleaned)
