from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AnalysisRecord, ApplicationRecord, TailoredResumeDraftRecord
from app.repositories.analyses import AnalysisRepository
from app.repositories.applications import ApplicationRepository
from app.repositories.tailored_resumes import TailoredResumeRepository
from app.schemas.auth import CurrentUser
from app.schemas.common import ValidationWarning
from app.schemas.job import JobProfile
from app.schemas.report import ApplicationReport, TailoredBullet
from app.schemas.resume import ResumeFact, ResumeProfile
from app.schemas.tailored_resume import (
    TailoredResumeDraftResponse,
    TailoredResumeDraftStatus,
    TailoredResumeItem,
    TailoredResumeItemStatus,
    TailoredResumeItemUpdateRequest,
)
from app.services.docx_resume_renderer import render_tailored_resume_docx
from app.services.latex_resume_renderer import render_tailored_resume_latex
from app.services.pdf_resume_compiler import (
    PdfCompilationFailed,
    PdfCompilationTimedOut,
    PdfCompilerBusy,
    PdfCompilerUnavailable,
    PdfOutputTooLarge,
    compile_latex_to_pdf,
)
from app.services.skill_normalizer import find_skills

MAX_DRAFT_ITEMS = 8
HIGH_RISK_CLAIM_TERMS = {
    "achieved",
    "award",
    "awarded",
    "certified",
    "certification",
    "enterprise",
    "leadership",
    "managed",
    "patent",
    "production",
    "revenue",
    "senior",
    "sla",
    "uptime",
}
METRIC_PATTERNS = (
    re.compile(r"\b\d+(?:\.\d+)?\s*%"),
    re.compile(r"\b\d+(?:\.\d+)?[xX]\b"),
    re.compile(r"\b\d+\+(?!\w)"),
    re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b"),
    re.compile(r"(?:[$€£]\s*)?\b\d+(?:,\d{3})*(?:\.\d+)?\s*[kKmMbB]\b"),
    re.compile(
        r"(?i)\b\d+(?:,\d{3})*(?:\.\d+)?\s+"
        r"(?:customers?|clients?|users?|requests?|records?|transactions?|"
        r"endpoints?|deployments?|teams?|engineers?|hours?|days?|weeks?|months?|years?)\b"
    ),
)


@dataclass(frozen=True)
class RenderedTailoredResume:
    content: str | bytes
    report_id: int


def get_or_create_tailored_resume_draft(
    db: Session,
    application_id: int,
    current_user: CurrentUser,
) -> TailoredResumeDraftResponse:
    application = _get_ready_application(db, application_id, current_user)
    repository = TailoredResumeRepository(db)
    draft = _current_draft_for_application(repository, application, current_user)
    if not draft:
        analysis = _get_analysis(db, application.report_id, current_user)
        draft = _create_draft_from_analysis(db, application, analysis, current_user)
    return _draft_response(draft)


def update_tailored_resume_item(
    db: Session,
    application_id: int,
    item_id: str,
    request: TailoredResumeItemUpdateRequest,
    current_user: CurrentUser,
) -> TailoredResumeDraftResponse:
    application = _get_ready_application(db, application_id, current_user)
    draft = _get_or_create_draft_record(db, application, current_user)
    analysis = _get_analysis(db, draft.report_id, current_user)
    resume = ResumeProfile.model_validate(analysis.resume.profile_json)
    items = _draft_items(draft)

    next_items: list[TailoredResumeItem] = []
    matched_item = False
    for item in items:
        if item.id != item_id:
            next_items.append(item)
            continue

        matched_item = True
        next_item = item.model_copy(deep=True)
        if request.reset_edited_bullet:
            next_item.edited_bullet = None
        elif request.edited_bullet is not None:
            next_item.edited_bullet = _clean_bullet(request.edited_bullet)
        if request.status is not None:
            next_item.status = request.status
        next_item.validation_warnings = _validate_draft_item(next_item, resume)
        if next_item.status == TailoredResumeItemStatus.accepted and next_item.validation_warnings:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": "Accepted resume bullet must be supported by linked evidence.",
                    "warnings": [
                        warning.model_dump(mode="json") for warning in next_item.validation_warnings
                    ],
                },
            )
        next_items.append(next_item)

    if not matched_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tailored resume item not found",
        )

    draft.items_json = [item.model_dump(mode="json") for item in next_items]
    draft.status = _draft_status(next_items).value
    saved = TailoredResumeRepository(db).save(draft)
    return _draft_response(saved)


def render_tailored_resume_latex_for_application(
    db: Session,
    application_id: int,
    current_user: CurrentUser,
) -> RenderedTailoredResume:
    report, resume, job, draft = _export_context(db, application_id, current_user)
    return RenderedTailoredResume(
        content=render_tailored_resume_latex(report=report, resume=resume, job=job),
        report_id=draft.report_id,
    )


def render_tailored_resume_docx_for_application(
    db: Session,
    application_id: int,
    current_user: CurrentUser,
) -> RenderedTailoredResume:
    report, resume, job, draft = _export_context(db, application_id, current_user)
    return RenderedTailoredResume(
        content=render_tailored_resume_docx(report=report, resume=resume, job=job),
        report_id=draft.report_id,
    )


def render_tailored_resume_pdf_for_application(
    db: Session,
    application_id: int,
    settings: Settings,
    current_user: CurrentUser,
) -> RenderedTailoredResume:
    rendered_latex = render_tailored_resume_latex_for_application(db, application_id, current_user)
    try:
        pdf = compile_latex_to_pdf(
            str(rendered_latex.content),
            timeout_seconds=settings.latex_compile_timeout_seconds,
            max_output_bytes=settings.latex_pdf_max_bytes,
        )
    except PdfCompilerUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF export requires tectonic or pdflatex on the server.",
        ) from exc
    except PdfCompilerBusy as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF compiler is busy. Retry the export shortly.",
            headers={"Retry-After": "2"},
        ) from exc
    except PdfCompilationTimedOut as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="PDF export timed out while compiling the generated resume.",
        ) from exc
    except PdfOutputTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Generated PDF exceeds the configured export size limit.",
        ) from exc
    except PdfCompilationFailed as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Generated LaTeX could not be compiled into PDF.",
        ) from exc
    return RenderedTailoredResume(content=pdf, report_id=rendered_latex.report_id)


def _get_ready_application(
    db: Session,
    application_id: int,
    current_user: CurrentUser,
) -> ApplicationRecord:
    application = ApplicationRepository(db).get(application_id, user_id=current_user.id)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if application.report_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Generate a report before opening the tailored resume workspace.",
        )
    return application


def _get_analysis(db: Session, report_id: int | None, current_user: CurrentUser) -> AnalysisRecord:
    if report_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    analysis = AnalysisRepository(db).get(report_id, user_id=current_user.id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return analysis


def _get_or_create_draft_record(
    db: Session,
    application: ApplicationRecord,
    current_user: CurrentUser,
) -> TailoredResumeDraftRecord:
    repository = TailoredResumeRepository(db)
    draft = _current_draft_for_application(repository, application, current_user)
    if draft:
        return draft
    return _create_draft_from_analysis(
        db,
        application,
        _get_analysis(db, application.report_id, current_user),
        current_user,
    )


def _create_draft_from_analysis(
    db: Session,
    application: ApplicationRecord,
    analysis: AnalysisRecord,
    current_user: CurrentUser,
) -> TailoredResumeDraftRecord:
    report = ApplicationReport.model_validate(analysis.report_json)
    resume = ResumeProfile.model_validate(analysis.resume.profile_json)
    facts_by_id = {fact.id: fact for fact in resume.facts}
    items = [
        _item_from_report_bullet(index, bullet, facts_by_id)
        for index, bullet in enumerate(report.tailored_bullets[:MAX_DRAFT_ITEMS], start=1)
    ]
    draft = TailoredResumeDraftRecord(
        user_id=current_user.id,
        application_id=application.id,
        report_id=analysis.id,
        status=TailoredResumeDraftStatus.draft.value,
        items_json=[item.model_dump(mode="json") for item in items],
    )
    repository = TailoredResumeRepository(db)
    return repository.add_or_get_by_application(draft)


def _current_draft_for_application(
    repository: TailoredResumeRepository,
    application: ApplicationRecord,
    current_user: CurrentUser,
) -> TailoredResumeDraftRecord | None:
    draft = repository.get_by_application_id(application.id, user_id=current_user.id)
    if draft and draft.report_id != application.report_id:
        repository.delete(draft)
        return None
    return draft


def _item_from_report_bullet(
    index: int,
    bullet: TailoredBullet,
    facts_by_id: dict[str, ResumeFact],
) -> TailoredResumeItem:
    evidence_texts = [
        facts_by_id[evidence_id].text
        for evidence_id in bullet.evidence_ids
        if evidence_id in facts_by_id
    ]
    item = TailoredResumeItem(
        id=f"bullet_{index:03d}",
        source_bullet=evidence_texts[0] if evidence_texts else bullet.bullet,
        suggested_bullet=bullet.bullet,
        evidence_ids=bullet.evidence_ids,
        evidence_labels=[_evidence_label(evidence_id) for evidence_id in bullet.evidence_ids],
        evidence_texts=evidence_texts,
        jd_keywords_used=bullet.jd_keywords_used,
        unsupported_claims=bullet.unsupported_claims,
    )
    resume = ResumeProfile(
        resume_id=0,
        candidate={},
        facts=list(facts_by_id.values()),
    )
    item.validation_warnings = _validate_draft_item(item, resume)
    return item


def _draft_response(draft: TailoredResumeDraftRecord) -> TailoredResumeDraftResponse:
    items = _draft_items(draft)
    accepted_count = sum(1 for item in items if item.status == TailoredResumeItemStatus.accepted)
    rejected_count = sum(1 for item in items if item.status == TailoredResumeItemStatus.rejected)
    pending_count = sum(1 for item in items if item.status == TailoredResumeItemStatus.pending)
    return TailoredResumeDraftResponse(
        id=draft.id,
        application_id=draft.application_id,
        report_id=draft.report_id,
        status=TailoredResumeDraftStatus(draft.status),
        items=items,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        pending_count=pending_count,
        export_ready=accepted_count > 0,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _draft_items(draft: TailoredResumeDraftRecord) -> list[TailoredResumeItem]:
    return [TailoredResumeItem.model_validate(item) for item in draft.items_json]


def _draft_status(items: list[TailoredResumeItem]) -> TailoredResumeDraftStatus:
    if not items:
        return TailoredResumeDraftStatus.draft
    if any(item.status == TailoredResumeItemStatus.pending for item in items):
        return TailoredResumeDraftStatus.draft
    return TailoredResumeDraftStatus.reviewed


def _export_context(
    db: Session,
    application_id: int,
    current_user: CurrentUser,
) -> tuple[ApplicationReport, ResumeProfile, JobProfile, TailoredResumeDraftRecord]:
    application = _get_ready_application(db, application_id, current_user)
    draft = _get_or_create_draft_record(db, application, current_user)
    analysis = _get_analysis(db, draft.report_id, current_user)
    resume = ResumeProfile.model_validate(analysis.resume.profile_json)
    job = JobProfile.model_validate(analysis.job.profile_json)
    items = _draft_items(draft)
    accepted_bullets = _accepted_tailored_bullets(items, resume)
    if not accepted_bullets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Accept at least one evidence-backed bullet before exporting.",
        )
    report = ApplicationReport.model_validate(analysis.report_json).model_copy(
        deep=True,
        update={"tailored_bullets": accepted_bullets},
    )
    return report, resume, job, draft


def _accepted_tailored_bullets(
    items: list[TailoredResumeItem],
    resume: ResumeProfile,
) -> list[TailoredBullet]:
    accepted: list[TailoredBullet] = []
    for item in items:
        if item.status != TailoredResumeItemStatus.accepted:
            continue
        warnings = _validate_draft_item(item, resume)
        if warnings:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": "Accepted resume bullet must be supported by linked evidence.",
                    "warnings": [warning.model_dump(mode="json") for warning in warnings],
                },
            )
        accepted.append(
            TailoredBullet(
                bullet=_effective_bullet(item),
                evidence_ids=item.evidence_ids,
                jd_keywords_used=item.jd_keywords_used,
                unsupported_claims=[],
            )
        )
    return accepted


def _validate_draft_item(
    item: TailoredResumeItem,
    resume: ResumeProfile,
) -> list[ValidationWarning]:
    facts_by_id = {fact.id: fact for fact in resume.facts}
    warnings: list[ValidationWarning] = []
    missing_ids = [
        evidence_id for evidence_id in item.evidence_ids if evidence_id not in facts_by_id
    ]
    if missing_ids:
        warnings.append(
            ValidationWarning(
                code="draft_bullet_missing_evidence",
                message="Draft bullet references unknown resume evidence.",
                evidence_ids=missing_ids,
            )
        )
    if item.unsupported_claims:
        warnings.append(
            ValidationWarning(
                code="draft_bullet_has_report_unsupported_claims",
                message="Report validation already marked this bullet as review-only.",
                evidence_ids=item.evidence_ids,
            )
        )

    evidence_text = " ".join(
        facts_by_id[evidence_id].text
        for evidence_id in item.evidence_ids
        if evidence_id in facts_by_id
    )
    edited_text = _effective_bullet(item)
    unsupported_skills = _unsupported_skills(
        edited_text,
        evidence_text=evidence_text,
    )
    if unsupported_skills:
        warnings.append(
            ValidationWarning(
                code="draft_bullet_has_unsupported_skill",
                message=(
                    "Draft bullet contains skills not found in linked evidence: "
                    f"{', '.join(unsupported_skills)}."
                ),
                evidence_ids=item.evidence_ids,
            )
        )

    unsupported_claims = _unsupported_claim_terms(edited_text, evidence_text)
    if unsupported_claims:
        warnings.append(
            ValidationWarning(
                code="draft_bullet_has_unsupported_claim",
                message=(
                    "Draft bullet adds claims not found in linked evidence: "
                    f"{', '.join(unsupported_claims)}."
                ),
                evidence_ids=item.evidence_ids,
            )
        )
    return warnings


def _unsupported_skills(
    text: str,
    *,
    evidence_text: str,
) -> list[str]:
    allowed_skills = set(find_skills(evidence_text))
    return [skill for skill in find_skills(text) if skill not in allowed_skills]


def _unsupported_claim_terms(text: str, evidence_text: str) -> list[str]:
    text_normalized = text.casefold()
    evidence_normalized = evidence_text.casefold()
    unsupported_terms = [
        term
        for term in sorted(HIGH_RISK_CLAIM_TERMS)
        if _contains_claim_term(text_normalized, term)
        and not _contains_claim_term(evidence_normalized, term)
    ]
    unsupported_metrics = [
        metric
        for metric in _metric_claims(text)
        if _normalize_claim_text(metric) not in _normalize_claim_text(evidence_text)
    ]
    return [*unsupported_terms, *unsupported_metrics]


def _contains_claim_term(value: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", value))


def _metric_claims(value: str) -> list[str]:
    claims: list[str] = []
    for pattern in METRIC_PATTERNS:
        for match in pattern.finditer(value):
            claim = match.group(0).strip()
            if claim and claim not in claims:
                claims.append(claim)
    return claims


def _normalize_claim_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).casefold().strip()


def _effective_bullet(item: TailoredResumeItem) -> str:
    return _clean_bullet(item.edited_bullet or item.suggested_bullet)


def _clean_bullet(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _evidence_label(evidence_id: str) -> str:
    labels = {
        "projects_": "Project evidence",
        "experience_": "Work evidence",
        "skills_": "Skills section",
        "summary_": "Resume summary",
        "education_": "Education evidence",
        "certifications_": "Certification evidence",
    }
    for prefix, label in labels.items():
        if evidence_id.startswith(prefix):
            return f"{label}{_evidence_number(evidence_id)}"
    return "Resume evidence"


def _evidence_number(evidence_id: str) -> str:
    match = re.search(r"_(\d+)$", evidence_id)
    if not match:
        return ""
    return f" #{int(match.group(1))}"
