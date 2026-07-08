import re
from contextlib import suppress
from typing import TYPE_CHECKING

import requests
from bs4 import BeautifulSoup
from fastapi import HTTPException, status

from app.schemas.common import Confidence, ValidationWarning
from app.schemas.job import JobProfile, JobSkill
from app.services.hashing import sha256_text
from app.services.skill_normalizer import find_skills
from app.services.text import clean_text, split_non_empty_lines

if TYPE_CHECKING:
    from app.core.config import Settings

REQUIRED_MARKERS = ("required", "requirements", "must have", "you have", "need to have")
PREFERRED_MARKERS = ("preferred", "nice to have", "bonus", "plus", "good to have")
RESPONSIBILITY_MARKERS = ("responsibilities", "what you will do", "you will", "role includes")
BENEFIT_MARKERS = ("benefits", "perks", "compensation")
MIN_FETCHED_TEXT_CHARS = 40


class JobParseError(ValueError):
    pass


class BrowserFallbackUnavailable(RuntimeError):
    pass


def fetch_job_text(job_url: str, *, settings: "Settings | None" = None) -> str:
    try:
        response = requests.get(
            job_url,
            timeout=10,
            headers={"User-Agent": "ResumePilot/0.1 (+local job analysis)"},
        )
        if response.status_code in {401, 403, 429}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Job URL is blocked, private, or rate limited. "
                    "Paste the job description text instead."
                ),
            )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Could not fetch job URL. Paste the job description text instead.",
        ) from exc

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    text = clean_text(soup.get_text("\n"))
    if len(text) < MIN_FETCHED_TEXT_CHARS:
        if settings and settings.enable_job_browser_fallback:
            try:
                browser_text = _fetch_job_text_with_playwright(
                    job_url,
                    timeout_ms=settings.job_browser_timeout_ms,
                )
            except BrowserFallbackUnavailable:
                browser_text = ""
            if len(browser_text) >= MIN_FETCHED_TEXT_CHARS:
                return browser_text
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Fetched job page did not contain enough readable text. "
                "Paste the job description instead, or install the optional "
                "Playwright Chromium browser for JavaScript-rendered public pages."
            ),
        )
    return text


def parse_job_profile(
    raw_text: str,
    *,
    job_id: int = 0,
    company: str | None = None,
    role: str | None = None,
) -> JobProfile:
    text = clean_text(raw_text)
    if len(text) < 40:
        raise JobParseError("Job description is too short to analyze")

    lines = split_non_empty_lines(text)
    company_name = company or _extract_company(lines)
    role_title = role or _extract_role(lines)
    experience_level = _extract_experience_level(text)
    required, preferred, keyword_skills = _extract_job_skills(lines)
    responsibilities = _extract_section_items(
        lines, RESPONSIBILITY_MARKERS, stop_markers=REQUIRED_MARKERS + BENEFIT_MARKERS
    )
    benefits = _extract_section_items(
        lines, BENEFIT_MARKERS, stop_markers=REQUIRED_MARKERS + RESPONSIBILITY_MARKERS
    )
    keywords = sorted(
        {*keyword_skills, *(skill.name for skill in required), *(skill.name for skill in preferred)}
    )
    warnings = _job_warnings(required, text)

    return JobProfile(
        job_id=job_id,
        company=company_name,
        role_title=role_title,
        required_skills=required,
        preferred_skills=preferred,
        responsibilities=responsibilities[:12],
        experience_level=experience_level,
        keywords=keywords,
        benefits=benefits[:8],
        warnings=warnings,
    )


def job_content_hash(raw_text: str) -> str:
    return sha256_text(clean_text(raw_text))


def _fetch_job_text_with_playwright(job_url: str, *, timeout_ms: int) -> str:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserFallbackUnavailable("Python Playwright package is not installed.") from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(job_url, wait_until="domcontentloaded", timeout=timeout_ms)
                with suppress(PlaywrightError):
                    page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5000))
                body_text = page.locator("body").inner_text(timeout=timeout_ms)
                return clean_text(body_text)
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise BrowserFallbackUnavailable("Playwright could not render the job URL.") from exc


def _extract_company(lines: list[str]) -> str | None:
    for line in lines[:12]:
        lowered = line.lower()
        if lowered.startswith("company:"):
            return line.split(":", 1)[1].strip() or None
        if " at " in lowered and len(line.split()) <= 12:
            return line.rsplit(" at ", 1)[-1].strip()
    return None


def _extract_role(lines: list[str]) -> str | None:
    for line in lines[:8]:
        lowered = line.lower()
        if lowered.startswith(("job title:", "role:", "position:")):
            return line.split(":", 1)[1].strip() or None
        if 2 <= len(line.split()) <= 10 and any(
            token in lowered
            for token in ("engineer", "developer", "analyst", "designer", "manager")
        ):
            return line
    return None


def _extract_experience_level(text: str) -> str | None:
    match = re.search(r"(\d+\s*\+?\s*(?:-|to)?\s*\d*)\s+years?", text, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1).replace(' ', '')} years"
    if re.search(r"\b(fresher|entry[- ]level|junior|intern)\b", text, flags=re.IGNORECASE):
        return "0-2 years"
    return None


def _extract_job_skills(lines: list[str]) -> tuple[list[JobSkill], list[JobSkill], list[str]]:
    required: dict[str, JobSkill] = {}
    preferred: dict[str, JobSkill] = {}
    keywords: set[str] = set()
    current_context = "keyword"

    for line in lines:
        lowered = line.lower()
        if any(marker in lowered for marker in REQUIRED_MARKERS):
            current_context = "required"
        elif any(marker in lowered for marker in PREFERRED_MARKERS):
            current_context = "preferred"

        skills = find_skills(line)
        if not skills:
            continue

        for skill in skills:
            if current_context == "required" or any(
                marker in lowered for marker in REQUIRED_MARKERS
            ):
                required.setdefault(
                    skill,
                    _job_skill(skill, "required", line, len(required) + 1, Confidence.high),
                )
            elif current_context == "preferred" or any(
                marker in lowered for marker in PREFERRED_MARKERS
            ):
                preferred.setdefault(
                    skill,
                    _job_skill(skill, "preferred", line, len(preferred) + 1, Confidence.medium),
                )
            else:
                keywords.add(skill)

    for skill in list(preferred):
        if skill in required:
            preferred.pop(skill)
    keywords -= set(required) | set(preferred)
    return list(required.values()), list(preferred.values()), sorted(keywords)


def _job_skill(
    skill: str, importance: str, evidence: str, index: int, confidence: Confidence
) -> JobSkill:
    return JobSkill(
        id=f"job_{importance}_{index:03d}",
        name=skill,
        importance=importance,
        evidence_text=evidence,
        confidence=confidence,
    )


def _extract_section_items(
    lines: list[str], markers: tuple[str, ...], *, stop_markers: tuple[str, ...]
) -> list[str]:
    items: list[str] = []
    in_section = False
    for line in lines:
        lowered = line.lower()
        if any(marker in lowered for marker in markers):
            in_section = True
            continue
        if in_section and any(marker in lowered for marker in stop_markers):
            break
        if in_section and len(line.split()) >= 4:
            items.append(line)
    return items


def _job_warnings(required: list[JobSkill], text: str) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    if not required:
        warnings.append(
            ValidationWarning(
                code="required_skills_unclear",
                message=(
                    "No explicit required skills were detected; match score may be conservative."
                ),
            )
        )
    if len(text) < 500:
        warnings.append(
            ValidationWarning(
                code="job_description_short",
                message="Job description is short; role details may be incomplete.",
            )
        )
    return warnings
