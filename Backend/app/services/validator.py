from app.schemas.common import ValidationWarning
from app.schemas.report import ApplicationReport
from app.schemas.resume import ResumeProfile
from app.services.skill_normalizer import find_skills


def validate_report_against_resume(
    report: ApplicationReport, resume: ResumeProfile
) -> list[ValidationWarning]:
    facts_by_id = {fact.id: fact for fact in resume.facts}
    resume_skill_names = {skill.name for skill in resume.skills}
    warnings: list[ValidationWarning] = []

    for matched in report.matched_skills:
        missing_ids = [
            evidence_id
            for evidence_id in matched.resume_evidence_ids
            if evidence_id not in facts_by_id
        ]
        if missing_ids:
            warnings.append(
                ValidationWarning(
                    code="matched_skill_missing_evidence",
                    message=f"Matched skill {matched.skill} references unknown evidence IDs.",
                    evidence_ids=missing_ids,
                )
            )

    for bullet in report.tailored_bullets:
        missing_ids = [
            evidence_id for evidence_id in bullet.evidence_ids if evidence_id not in facts_by_id
        ]
        if missing_ids:
            warnings.append(
                ValidationWarning(
                    code="bullet_missing_evidence",
                    message="Tailored bullet references unknown evidence IDs.",
                    evidence_ids=missing_ids,
                )
            )
        unsupported_skills = [
            skill
            for skill in find_skills(bullet.bullet)
            if skill not in resume_skill_names and skill not in bullet.jd_keywords_used
        ]
        if unsupported_skills:
            warnings.append(
                ValidationWarning(
                    code="bullet_has_unsupported_skill",
                    message=(
                        "Tailored bullet contains unsupported skills: "
                        f"{', '.join(unsupported_skills)}."
                    ),
                    evidence_ids=bullet.evidence_ids,
                )
            )

    for keyword in report.ats_keywords:
        if keyword.status == "supported" and not keyword.evidence_ids:
            warnings.append(
                ValidationWarning(
                    code="supported_keyword_missing_evidence",
                    message=f"Supported keyword {keyword.keyword} has no evidence IDs.",
                )
            )

    return warnings
