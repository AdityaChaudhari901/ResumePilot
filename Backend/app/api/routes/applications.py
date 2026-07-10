from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings
from app.core.config import Settings
from app.db.models import ApplicationRecord, TailoredResumeDraftRecord
from app.schemas.application import (
    ApplicationDetail,
    ApplicationDraftRequest,
    ApplicationItem,
    ApplicationListResponse,
    ApplicationStatus,
    ApplicationStatusUpdateRequest,
)
from app.schemas.auth import CurrentUser
from app.schemas.operation import WorkflowJobResponse
from app.schemas.tailored_resume import (
    TailoredResumeDraftResponse,
    TailoredResumeDraftStatus,
    TailoredResumeItemUpdateRequest,
)
from app.services.application_service import (
    create_application_draft,
    get_application,
    list_applications,
    update_application_status,
)
from app.services.audit_service import add_audit_event
from app.services.tailored_resume_service import (
    get_or_create_tailored_resume_draft,
    render_tailored_resume_docx_for_application,
    render_tailored_resume_latex_for_application,
    update_tailored_resume_item,
)
from app.services.usage_service import reserve_export_usage
from app.services.workflow_job_service import (
    enqueue_pdf_export_job,
    execute_workflow_job,
    workflow_job_response,
)

router = APIRouter(prefix="/applications", tags=["applications"])
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("", response_model=ApplicationListResponse)
def read_applications(
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApplicationListResponse:
    return list_applications(db, current_user, limit=limit)


@router.post("", response_model=ApplicationItem, status_code=201)
def create_application(
    request: ApplicationDraftRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApplicationItem:
    return create_application_draft(db, request, current_user)


@router.get("/{application_id}", response_model=ApplicationDetail)
def read_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApplicationDetail:
    return get_application(db, application_id, current_user)


@router.patch("/{application_id}/status", response_model=ApplicationItem)
def change_application_status(
    application_id: int,
    request: ApplicationStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApplicationItem:
    return update_application_status(db, application_id, request, current_user)


@router.get("/{application_id}/tailored-resume", response_model=TailoredResumeDraftResponse)
def read_tailored_resume_draft(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TailoredResumeDraftResponse:
    return get_or_create_tailored_resume_draft(db, application_id, current_user)


@router.patch(
    "/{application_id}/tailored-resume/items/{item_id}",
    response_model=TailoredResumeDraftResponse,
)
def change_tailored_resume_item(
    application_id: int,
    item_id: str,
    request: TailoredResumeItemUpdateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TailoredResumeDraftResponse:
    return update_tailored_resume_item(db, application_id, item_id, request, current_user)


@router.post("/{application_id}/tailored-resume/latex", response_class=PlainTextResponse)
def read_reviewed_tailored_resume_latex(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PlainTextResponse:
    rendered = render_tailored_resume_latex_for_application(db, application_id, current_user)
    _finalize_tailored_resume_export(db, current_user, application_id, rendered.report_id, "latex")
    return PlainTextResponse(
        content=str(rendered.content),
        media_type="application/x-tex",
        headers=_download_headers(f"resumepilot-application-{application_id}.tex"),
    )


@router.post("/{application_id}/tailored-resume/docx")
def read_reviewed_tailored_resume_docx(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    rendered = render_tailored_resume_docx_for_application(db, application_id, current_user)
    _finalize_tailored_resume_export(db, current_user, application_id, rendered.report_id, "docx")
    return Response(
        content=bytes(rendered.content),
        media_type=DOCX_MEDIA_TYPE,
        headers=_download_headers(f"resumepilot-application-{application_id}.docx"),
    )


@router.post(
    "/{application_id}/tailored-resume/pdf",
    response_model=WorkflowJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def read_reviewed_tailored_resume_pdf(
    application_id: int,
    request: Request,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowJobResponse:
    operation, created = enqueue_pdf_export_job(
        db,
        application_id,
        current_user,
        idempotency_key=idempotency_key,
        request_id=getattr(request.state, "request_id", None),
        max_attempts=min(settings.workflow_job_max_attempts, 2),
    )
    if created and settings.execute_workflow_jobs_inline:
        operation = execute_workflow_job(
            db,
            operation.id,
            settings=settings,
            worker_id=f"inline-{operation.id}",
        )
    response.headers["Location"] = f"/operations/{operation.id}"
    response.headers["Retry-After"] = "1"
    return workflow_job_response(operation)


def _finalize_tailored_resume_export(
    db: Session,
    current_user: CurrentUser,
    application_id: int,
    report_id: int,
    export_format: str,
) -> None:
    application = db.scalar(
        select(ApplicationRecord)
        .where(
            ApplicationRecord.id == application_id,
            ApplicationRecord.user_id == current_user.id,
        )
        .with_for_update()
    )
    draft = db.scalar(
        select(TailoredResumeDraftRecord)
        .where(
            TailoredResumeDraftRecord.application_id == application_id,
            TailoredResumeDraftRecord.user_id == current_user.id,
        )
        .with_for_update()
    )
    if (
        not application
        or application.report_id != report_id
        or not draft
        or draft.report_id != report_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The tailored resume changed while the export was being prepared. Retry the export."
            ),
        )

    reserve_export_usage(db, current_user, report_id=report_id, export_format=export_format)
    add_audit_event(
        db,
        event_type="tailored_resume.exported",
        user_id=current_user.id,
        payload={
            "application_id": application_id,
            "report_id": report_id,
            "format": export_format,
        },
    )
    draft.status = TailoredResumeDraftStatus.exported.value
    if application.status != ApplicationStatus.applied.value:
        application.status = ApplicationStatus.exported.value
    db.add(draft)
    db.add(application)
    db.commit()


def _download_headers(filename: str) -> dict[str, str]:
    return {
        "Cache-Control": "private, no-store",
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Content-Type-Options": "nosniff",
    }
