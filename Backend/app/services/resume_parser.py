import re
from io import BytesIO

from app.schemas.common import Confidence, ValidationWarning
from app.schemas.resume import CandidateProfile, ResumeFact, ResumeProfile, ResumeSkill
from app.services.resume_evidence import starts_with_resume_action_verb
from app.services.skill_normalizer import category_for_skill, find_skills
from app.services.text import clean_text, detect_section, evidence_id, split_non_empty_lines

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
URL_RE = re.compile(r"https?://[^\s)>\]]+")
BULLET_PREFIX_RE = re.compile(
    r"^\s*(?:(?:[-*]|\d+[.)])\s+|"
    r"[\u2022\u2023\u2043\u2219\u25aa\u25ab\u25a0\u25a1\u25cf\u25e6\uf0b7]\s*)"
)
SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]*$")
TRAILING_CONNECTOR_RE = re.compile(
    r"(?:\b(?:a|an|and|as|at|by|for|from|in|of|on|or|the|to|using|via|with)|[,;:/&-])$",
    re.IGNORECASE,
)
CONTINUATION_START_RE = re.compile(
    r"^(?:[a-z(,;:/&-]|(?i:and\b|as\b|by\b|for\b|from\b|in\b|including\b|of\b|on\b|"
    r"or\b|resulting\b|that\b|through\b|to\b|using\b|via\b|which\b|while\b|with\b))"
)
WRAPPED_LINE_MIN_LENGTH = 45
WRAPPED_FACT_SECTIONS = {"summary", "experience", "projects"}
MAX_RESUME_PDF_PAGES = 50
MAX_EXTRACTED_RESUME_CHARS = 1_000_000


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
    facts = _build_facts(text.splitlines())
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
        from pypdf.errors import PdfReadError
    except ImportError as exc:  # pragma: no cover - dependency exists in normal install
        raise ResumeParseError("PDF parsing dependency is not installed") from exc

    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise ResumeParseError("Encrypted PDF resumes are not supported")
        if len(reader.pages) > MAX_RESUME_PDF_PAGES:
            raise ResumeParseError(
                f"PDF resume exceeds the {MAX_RESUME_PDF_PAGES}-page processing limit"
            )
        page_text: list[str] = []
        extracted_chars = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            extracted_chars += len(text)
            if extracted_chars > MAX_EXTRACTED_RESUME_CHARS:
                raise ResumeParseError("PDF resume expands beyond the safe text limit")
            page_text.append(text)
        return "\n".join(page_text)
    except ResumeParseError:
        raise
    except (PdfReadError, ValueError) as exc:
        raise ResumeParseError("PDF resume could not be parsed safely") from exc


def _extract_docx_text(content: bytes) -> str:
    try:
        from docx import Document
        from docx.opc.exceptions import PackageNotFoundError
    except ImportError as exc:  # pragma: no cover - dependency exists in normal install
        raise ResumeParseError("DOCX parsing dependency is not installed") from exc

    try:
        document = Document(BytesIO(content))
    except ResumeParseError:
        raise
    except (PackageNotFoundError, ValueError) as exc:
        raise ResumeParseError("DOCX resume could not be parsed safely") from exc
    text = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
    if len(text) > MAX_EXTRACTED_RESUME_CHARS:
        raise ResumeParseError("DOCX resume expands beyond the safe text limit")
    return text


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
    pending_text: str | None = None
    pending_section = current_section
    pending_is_bullet = False

    def flush_pending() -> None:
        nonlocal pending_text
        if not pending_text:
            return
        section_counts[pending_section] = section_counts.get(pending_section, 0) + 1
        confidence = (
            Confidence.high if pending_section in {"experience", "projects"} else Confidence.medium
        )
        facts.append(
            ResumeFact(
                id=evidence_id(pending_section, section_counts[pending_section]),
                text=pending_text,
                section=pending_section,
                confidence=confidence,
            )
        )
        pending_text = None

    for raw_line in lines:
        if not raw_line.strip():
            flush_pending()
            continue

        line, is_bullet = _normalize_resume_line(raw_line)
        if not line:
            continue
        detected = detect_section(line)
        if detected:
            flush_pending()
            current_section = detected
            continue
        if _is_contact_noise(line):
            flush_pending()
            continue

        if pending_text and _should_join_wrapped_line(
            previous=pending_text,
            current=line,
            section=current_section,
            previous_is_bullet=pending_is_bullet,
            current_is_bullet=is_bullet,
        ):
            pending_text = _join_wrapped_lines(pending_text, line)
            continue

        flush_pending()
        pending_text = line
        pending_section = current_section
        pending_is_bullet = is_bullet

    flush_pending()
    return facts


def _normalize_resume_line(raw_line: str) -> tuple[str, bool]:
    stripped = raw_line.strip()
    bullet_match = BULLET_PREFIX_RE.match(stripped)
    if bullet_match:
        return stripped[bullet_match.end() :].strip(), True
    return stripped.lstrip("#\t "), False


def _should_join_wrapped_line(
    *,
    previous: str,
    current: str,
    section: str,
    previous_is_bullet: bool,
    current_is_bullet: bool,
) -> bool:
    if section not in WRAPPED_FACT_SECTIONS or current_is_bullet:
        return False
    if starts_with_resume_action_verb(current):
        return False

    starts_as_continuation = bool(CONTINUATION_START_RE.match(current))
    if SENTENCE_END_RE.search(previous):
        return section == "summary" and starts_as_continuation
    if previous_is_bullet or starts_as_continuation:
        return True
    return bool(TRAILING_CONNECTOR_RE.search(previous) or len(previous) >= WRAPPED_LINE_MIN_LENGTH)


def _join_wrapped_lines(previous: str, current: str) -> str:
    if previous.endswith("-") and current[:1].islower():
        return f"{previous[:-1]}{current}"
    return f"{previous} {current}"


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
