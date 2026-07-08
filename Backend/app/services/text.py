import re

SECTION_ALIASES: dict[str, str] = {
    "summary": "summary",
    "profile": "summary",
    "skills": "skills",
    "technical skills": "skills",
    "work experience": "experience",
    "experience": "experience",
    "employment": "experience",
    "projects": "projects",
    "project experience": "projects",
    "education": "education",
    "certifications": "certifications",
    "certificates": "certifications",
}


def clean_text(value: str) -> str:
    value = value.replace("\x00", "")
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def normalize_token(value: str) -> str:
    normalized = value.lower().strip()
    normalized = re.sub(r"[^a-z0-9+#./ -]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def split_non_empty_lines(text: str) -> list[str]:
    return [line.strip(" -*#\t") for line in text.splitlines() if line.strip(" -*#\t")]


def detect_section(line: str) -> str | None:
    cleaned = normalize_token(line).strip(":")
    return SECTION_ALIASES.get(cleaned)


def evidence_id(section: str, index: int) -> str:
    safe_section = re.sub(r"[^a-z0-9]+", "_", section.lower()).strip("_") or "fact"
    return f"{safe_section}_{index:03d}"
