import re
from io import BytesIO

from app.schemas.common import Confidence, ValidationWarning
from app.schemas.resume import CandidateProfile, ResumeFact, ResumeProfile, ResumeSkill
from app.services.skill_normalizer import category_for_skill, find_skills
from app.services.text import clean_text, detect_section, evidence_id, split_non_empty_lines

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
URL_RE = re.compile(r"https?://[^\s)>\]]+")


class ResumeParseError(ValueError):
    pass


def extract_resume_text(content: bytes, extension: str) -> str:
    extension = extension.lower()
    if extension in {".txt", ".md", ".markdown"}:
        return clean_text(content.decode("utf-8", errors="replace"))
    if extension == ".pdf":
        return clean_text(_extract_pdf_text(content))
    if extension == ".docx":
        return clean_text(_extract_docx_text(content))
    raise ResumeParseError(f"Unsupported resume extension: {extension}")


def parse_resume_profile(raw_text: str, resume_id: int = 0) -> ResumeProfile:
    text = clean_text(raw_text)
    if not text:
        raise ResumeParseError("Resume text is empty after extraction")

    lines = split_non_empty_lines(text)
    candidate = _parse_candidate(lines)
    facts = _build_facts(lines)
    skills = _extract_resume_skills(text, facts)
    warnings = _resume_warnings(candidate, facts, skills)

    return ResumeProfile(
        resume_id=resume_id,
        candidate=candidate,
        skills=skills,
        experience=[fact for fact in facts if fact.section == "experience"],
        projects=[fact for fact in facts if fact.section == "projects"],
        education=[fact for fact in facts if fact.section == "education"],
        certifications=[fact for fact in facts if fact.section == "certifications"],
        facts=facts,
        warnings=warnings,
    )


def _extract_pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency exists in normal install
        raise ResumeParseError("PDF parsing dependency is not installed") from exc

    reader = PdfReader(BytesIO(content))
    page_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(page_text)


def _extract_docx_text(content: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - dependency exists in normal install
        raise ResumeParseError("DOCX parsing dependency is not installed") from exc

    document = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())


def _parse_candidate(lines: list[str]) -> CandidateProfile:
    joined = "\n".join(lines[:12])
    email_match = EMAIL_RE.search(joined)
    phone_match = PHONE_RE.search(joined)
    links = [match.rstrip(".,") for match in URL_RE.findall(joined)]
    name = _guess_name(lines)
    return CandidateProfile(
        name=name,
        email=email_match.group(0) if email_match else None,
        phone=phone_match.group(0).strip() if phone_match else None,
        links=links,
    )


def _guess_name(lines: list[str]) -> str | None:
    for line in lines[:8]:
        if EMAIL_RE.search(line) or URL_RE.search(line) or PHONE_RE.search(line):
            continue
        if detect_section(line):
            continue
        if 1 <= len(line.split()) <= 5 and len(line) <= 80:
            return line
    return None


def _build_facts(lines: list[str]) -> list[ResumeFact]:
    facts: list[ResumeFact] = []
    section_counts: dict[str, int] = {}
    current_section = "summary"

    for line in lines:
        detected = detect_section(line)
        if detected:
            current_section = detected
            continue
        if _is_contact_noise(line):
            continue
        section_counts[current_section] = section_counts.get(current_section, 0) + 1
        confidence = (
            Confidence.high if current_section in {"experience", "projects"} else Confidence.medium
        )
        facts.append(
            ResumeFact(
                id=evidence_id(current_section, section_counts[current_section]),
                text=line,
                section=current_section,
                confidence=confidence,
            )
        )
    return facts


def _is_contact_noise(line: str) -> bool:
    return bool(EMAIL_RE.fullmatch(line) or URL_RE.fullmatch(line) or PHONE_RE.fullmatch(line))


def _extract_resume_skills(text: str, facts: list[ResumeFact]) -> list[ResumeSkill]:
    extracted = find_skills(text)
    skills: list[ResumeSkill] = []
    for skill in extracted:
        evidence_ids = [fact.id for fact in facts if skill in find_skills(fact.text)]
        if not evidence_ids:
            continue
        sections = {fact.section for fact in facts if fact.id in evidence_ids}
        confidence = Confidence.high if sections & {"experience", "projects"} else Confidence.medium
        skills.append(
            ResumeSkill(
                name=skill,
                category=category_for_skill(skill),
                evidence_ids=evidence_ids,
                confidence=confidence,
            )
        )
    return skills


def _resume_warnings(
    candidate: CandidateProfile, facts: list[ResumeFact], skills: list[ResumeSkill]
) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    if not candidate.name:
        warnings.append(
            ValidationWarning(
                code="candidate_name_missing", message="Candidate name was not detected."
            )
        )
    if not candidate.email:
        warnings.append(
            ValidationWarning(
                code="candidate_email_missing", message="Candidate email was not detected."
            )
        )
    if not facts:
        warnings.append(
            ValidationWarning(
                code="resume_facts_missing", message="No resume evidence facts were detected."
            )
        )
    if not skills:
        warnings.append(
            ValidationWarning(
                code="skills_missing", message="No known technical skills were detected."
            )
        )
    return warnings
