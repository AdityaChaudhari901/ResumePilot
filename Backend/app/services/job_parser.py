import ipaddress
import json
import re
import socket
from contextlib import suppress
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

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
EXPERIENCE_SECTION_MARKERS = (
    "experience requirements",
    "minimum qualifications",
    "qualifications",
    "requirements",
    "what you bring",
    "what we're looking for",
    "what we are looking for",
    "who you are",
)
NON_REQUIREMENT_SECTION_MARKERS = (
    "about us",
    "about the company",
    "company overview",
    *RESPONSIBILITY_MARKERS,
    *BENEFIT_MARKERS,
)
EXPLICIT_EXPERIENCE_REQUIREMENT_MARKERS = (
    "at least",
    "at most",
    "minimum",
    "maximum",
    "up to",
    "less than",
    "fewer than",
    "no more than",
    "required",
    "must have",
    "should have",
    "need to have",
    "needs to have",
    "you have",
    "you bring",
)
EXPERIENCE_BETWEEN_PATTERN = re.compile(
    r"\bbetween\s+(?P<minimum>\d+(?:\.\d+)?)\s+and\s+"
    r"(?P<maximum>\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b",
    re.IGNORECASE,
)
EXPERIENCE_UPPER_BOUND_PATTERN = re.compile(
    r"\b(?:(?:at\s+most|up\s+to|less\s+than|fewer\s+than|no\s+more\s+than|"
    r"max(?:imum)?(?:\s+of)?)\s+\d+(?:\.\d+)?\s*(?:years?|yrs?)|"
    r"\d+(?:\.\d+)?\s*(?:years?|yrs?)"
    r"(?:\s+(?:of\s+)?(?:[a-z-]+\s+){0,5}experience)?"
    r"\s+(?:or\s+less|max(?:imum)?))\b",
    re.IGNORECASE,
)
EXPERIENCE_YEARS_PATTERN = re.compile(
    r"\b(?P<claim>\d+(?:\.\d+)?\s*\+?\s*"
    r"(?:(?:-|–|—|to)\s*\d+(?:\.\d+)?)?)\)?\s*(?:years?|yrs?)\b",
    re.IGNORECASE,
)
COLLECTIVE_EXPERIENCE_PATTERN = re.compile(
    r"\b(?:combined|collective|collectively)\b|"
    r"\b(?:team|group|company|organization|department|colleagues?)\b"
    r"[^.!?]{0,40}\b(?:with|bringing|brings|has|have)\b|"
    r"\b(?:mentored|managed|led|supervised|collaborated\s+with)\s+"
    r"(?:engineers?|applicants?|consultants?)\s+with\b|"
    r"\b(?:managing|mentoring|supporting|leading|supervising|collaborating\s+with)\s+"
    r"(?:[a-z-]+\s+){0,2}(?:engineers?|developers?|customers?|clients?|consultants?)\s+"
    r"(?:with|bringing|who\s+have)\b|"
    r"\b(?:years?|yrs?)\b[^.!?]{0,50}\b(?:across|among)\s+"
    r"(?:(?:our|the)\s+)?(?:engineering\s+)?"
    r"(?:team|company|organization|department|consultants?|engineers?|applicants?)\b",
    re.IGNORECASE,
)
ENTRY_LEVEL_ROLE_PATTERN = re.compile(
    r"\b(?:fresher|entry[- ]level|junior|intern(?:ship)?)\b",
    re.IGNORECASE,
)
SENIOR_ROLE_PATTERN = re.compile(
    r"\b(?:senior|lead|principal|staff|manager|head|director)\b",
    re.IGNORECASE,
)
EXPERIENCE_REQUIREMENT_UNCLEAR = "requirement unclear"
MIN_FETCHED_TEXT_CHARS = 40
MAX_FETCHED_JOB_BYTES = 2 * 1024 * 1024
MAX_JOB_REDIRECTS = 3
JOB_FETCH_TIMEOUT = (3.0, 7.0)
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
ALLOWED_JOB_CONTENT_TYPES = {"application/xhtml+xml", "text/html", "text/plain"}


class JobParseError(ValueError):
    pass


class BrowserFallbackUnavailable(RuntimeError):
    pass


def fetch_job_text(job_url: str, *, settings: "Settings | None" = None) -> str:
    current_url = job_url
    try:
        for redirect_count in range(MAX_JOB_REDIRECTS + 1):
            allowed_ips = _assert_public_job_url(current_url)
            response = requests.get(
                current_url,
                timeout=JOB_FETCH_TIMEOUT,
                headers={
                    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
                    "User-Agent": "ResumePilot/0.1 (+local job analysis)",
                },
                allow_redirects=False,
                stream=True,
            )
            try:
                _assert_public_peer(response, allowed_ips)
                if response.status_code in REDIRECT_STATUS_CODES:
                    if redirect_count == MAX_JOB_REDIRECTS:
                        raise JobParseError("Job URL redirected too many times")
                    location = response.headers.get("location")
                    if not location:
                        raise JobParseError("Job URL returned an invalid redirect")
                    current_url = urljoin(current_url, location)
                    continue
                if response.status_code in {401, 403, 429}:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=(
                            "Job URL is blocked, private, or rate limited. "
                            "Paste the job description text instead."
                        ),
                    )
                response.raise_for_status()
                html = _read_bounded_job_response(response)
                break
            finally:
                response.close()
        else:  # pragma: no cover - loop always exits or raises
            raise JobParseError("Job URL could not be fetched")
    except JobParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{exc}. Paste the job description text instead.",
        ) from exc
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Could not fetch job URL. Paste the job description text instead.",
        ) from exc

    text = _html_to_job_text(html, current_url)
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


def _assert_public_job_url(
    job_url: str,
) -> frozenset[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    parsed = urlparse(job_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise JobParseError("Job URL must use public HTTP or HTTPS")
    if parsed.username or parsed.password:
        raise JobParseError("Job URL credentials are not allowed")

    hostname = parsed.hostname.rstrip(".").casefold()
    if hostname == "localhost" or hostname.endswith(
        (".localhost", ".local", ".internal", ".home.arpa")
    ):
        raise JobParseError("Job URL must not target a private host")

    try:
        resolved = {
            ipaddress.ip_address(result[4][0])
            for result in socket.getaddrinfo(
                hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        }
    except (OSError, ValueError) as exc:
        raise JobParseError("Job URL hostname could not be resolved") from exc
    if not resolved or any(not address.is_global for address in resolved):
        raise JobParseError("Job URL must not resolve to a private or reserved address")
    return frozenset(resolved)


def _assert_public_peer(
    response: requests.Response,
    allowed_ips: frozenset[ipaddress.IPv4Address | ipaddress.IPv6Address],
) -> None:
    connection = getattr(response.raw, "_connection", None)
    socket_connection = getattr(connection, "sock", None)
    if socket_connection is None:
        raise JobParseError("Job URL connection could not be verified")
    try:
        peer_address = ipaddress.ip_address(socket_connection.getpeername()[0])
    except (OSError, ValueError, TypeError) as exc:
        raise JobParseError("Job URL connection could not be verified") from exc
    if not peer_address.is_global or peer_address not in allowed_ips:
        raise JobParseError("Job URL connection changed to an untrusted address")


def _read_bounded_job_response(response: requests.Response) -> str:
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in ALLOWED_JOB_CONTENT_TYPES:
        raise JobParseError("Job URL did not return readable HTML or text")
    content_length = response.headers.get("content-length")
    if content_length:
        try:
            parsed_content_length = int(content_length)
        except ValueError as exc:
            raise JobParseError("Job URL returned an invalid content length") from exc
        if parsed_content_length > MAX_FETCHED_JOB_BYTES:
            raise JobParseError("Job page is too large")

    content = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024):
        content.extend(chunk)
        if len(content) > MAX_FETCHED_JOB_BYTES:
            raise JobParseError("Job page is too large")
    encoding = response.encoding or "utf-8"
    return bytes(content).decode(encoding, errors="replace")


def _html_to_job_text(html: str, job_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    structured_text = _extract_json_ld_job_posting_text(soup)
    if structured_text:
        return structured_text

    for element in soup(["script", "style", "noscript"]):
        element.decompose()

    container = _select_job_container(soup, job_url)
    return clean_text(container.get_text("\n"))


def _extract_json_ld_job_posting_text(soup: BeautifulSoup) -> str:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        content = script.string or script.get_text()
        if not content:
            continue
        for item in _json_ld_items(content):
            if not _is_job_posting_item(item):
                continue
            lines = _job_posting_lines(item)
            if lines:
                return clean_text("\n".join(lines))
    return ""


def _json_ld_items(content: str) -> list[dict]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return []
    values = payload if isinstance(payload, list) else [payload]
    items: list[dict] = []
    for value in values:
        if isinstance(value, dict) and isinstance(value.get("@graph"), list):
            items.extend(item for item in value["@graph"] if isinstance(item, dict))
        elif isinstance(value, dict):
            items.append(value)
    return items


def _is_job_posting_item(item: dict) -> bool:
    item_type = item.get("@type")
    if isinstance(item_type, list):
        return any(str(value).casefold() == "jobposting" for value in item_type)
    return str(item_type).casefold() == "jobposting"


def _job_posting_lines(item: dict) -> list[str]:
    lines: list[str] = []
    title = item.get("title")
    if isinstance(title, str):
        lines.append(f"Role: {title}")
    organization = item.get("hiringOrganization")
    if isinstance(organization, dict) and isinstance(organization.get("name"), str):
        lines.append(f"Company: {organization['name']}")
    employment_type = item.get("employmentType")
    if isinstance(employment_type, str):
        lines.append(f"Employment type: {employment_type}")
    experience = item.get("experienceRequirements")
    if isinstance(experience, str):
        lines.append(f"Experience: {experience}")
    description = item.get("description")
    if isinstance(description, str):
        description_text = BeautifulSoup(description, "html.parser").get_text("\n")
        lines.append(description_text)
    return lines


def _select_job_container(soup: BeautifulSoup, job_url: str):
    hostname = urlparse(job_url).hostname or ""
    selectors = _ats_container_selectors(hostname)
    for selector in selectors:
        candidate = soup.select_one(selector)
        if candidate and len(clean_text(candidate.get_text(" "))) >= MIN_FETCHED_TEXT_CHARS:
            return candidate
    return soup.body or soup


def _ats_container_selectors(hostname: str) -> tuple[str, ...]:
    if "greenhouse.io" in hostname:
        return ("#content", "main", "[data-qa='job-description']")
    if "lever.co" in hostname:
        return (".posting", ".content", "main")
    if "rippling.com" in hostname:
        return ("main", "[data-testid*='job']", "article")
    if "myworkdayjobs.com" in hostname or "workdayjobs.com" in hostname:
        return ("main", "[data-automation-id='jobPostingDescription']", "article")
    return ("main", "article", "[role='main']")


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
    experience_level = _extract_experience_level(lines, role_title=role_title)
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
                context = browser.new_context(service_workers="block")
                page = context.new_page()

                def guard_request(route) -> None:
                    request_url = route.request.url
                    if urlparse(request_url).scheme in {"blob", "data"}:
                        route.continue_()
                        return
                    try:
                        _assert_public_job_url(request_url)
                    except JobParseError:
                        route.abort("blockedbyclient")
                        return
                    route.continue_()

                page.route("**/*", guard_request)
                page.goto(job_url, wait_until="domcontentloaded", timeout=timeout_ms)
                _assert_public_job_url(page.url)
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


def _extract_experience_level(lines: list[str], *, role_title: str | None) -> str | None:
    claims: set[str] = set()
    section_context = "neutral"
    saw_experience_requirement = False
    for line in lines:
        lowered = line.casefold()
        declares_preferred = any(marker in lowered for marker in PREFERRED_MARKERS)
        if declares_preferred:
            section_context = "preferred"
        elif any(marker in lowered for marker in NON_REQUIREMENT_SECTION_MARKERS):
            section_context = "non_requirement"
        elif any(marker in lowered for marker in EXPERIENCE_SECTION_MARKERS):
            section_context = "required"

        for clause in re.split(r"\s*;\s*", line):
            lowered_clause = clause.casefold()
            clause_declares_preferred = any(
                marker in lowered_clause for marker in PREFERRED_MARKERS
            )
            if clause_declares_preferred:
                continue
            is_explicit_requirement = _has_explicit_experience_requirement(lowered_clause)
            inherited_non_requirement = section_context in {"preferred", "non_requirement"}
            if inherited_non_requirement and not is_explicit_requirement:
                continue
            if COLLECTIVE_EXPERIENCE_PATTERN.search(lowered_clause):
                if section_context == "required" or is_explicit_requirement:
                    saw_experience_requirement = True
                continue
            if not _is_candidate_experience_requirement(
                lowered_clause,
                in_requirements=section_context == "required",
            ):
                continue
            saw_experience_requirement = True
            claims.update(_experience_claims(clause))

    if len(claims) == 1:
        return f"{claims.pop()} years"
    if len(claims) > 1 or saw_experience_requirement:
        return EXPERIENCE_REQUIREMENT_UNCLEAR

    if _is_entry_level_role(role_title):
        return "0-2 years"
    return None


def _is_candidate_experience_requirement(line: str, *, in_requirements: bool) -> bool:
    if not re.search(r"\b(?:years?|yrs?)\b", line):
        return False
    if COLLECTIVE_EXPERIENCE_PATTERN.search(line):
        return False
    has_experience_word = "experience" in line
    starts_with_experience = bool(re.match(r"^\s*(?:[-*•]\s*)?experience\s*:", line))
    starts_with_tenure = bool(
        re.match(
            r"^\s*(?:[-*•]\s*)?(?:over\s+|more\s+than\s+)?\d+(?:\.\d+)?\s*\+?\s*"
            r"(?:years?|yrs?)\b",
            line,
        )
    )
    return has_experience_word and (
        starts_with_experience
        or starts_with_tenure
        or _has_explicit_experience_requirement(line)
        or in_requirements
    )


def _has_explicit_experience_requirement(line: str) -> bool:
    has_explicit_marker = any(marker in line for marker in EXPLICIT_EXPERIENCE_REQUIREMENT_MARKERS)
    subject_requirement = bool(
        re.search(
            r"\b(?:candidate|applicant|you)\s+(?:must\s+|should\s+|need(?:s)?\s+to\s+)?"
            r"(?:have|bring|possess|offer)\b",
            line,
        )
    )
    required_suffix = bool(re.search(r"\b(?:years?|yrs?)\b[^.!?]{0,30}\brequired\b", line))
    return has_explicit_marker or subject_requirement or required_suffix


def _experience_claims(line: str) -> set[str]:
    if EXPERIENCE_UPPER_BOUND_PATTERN.search(line):
        return set()
    between = EXPERIENCE_BETWEEN_PATTERN.search(line)
    if between:
        minimum = between.group("minimum")
        maximum = between.group("maximum")
        return {f"{minimum}-{maximum}"}
    return {
        _normalize_experience_claim(match.group("claim"))
        for match in EXPERIENCE_YEARS_PATTERN.finditer(line)
    }


def _normalize_experience_claim(value: str) -> str:
    normalized = re.sub(r"\s+", "", value.casefold()).replace("to", "-")
    return normalized.replace("–", "-").replace("—", "-")


def _is_entry_level_role(role_title: str | None) -> bool:
    if not role_title:
        return False
    if re.match(r"^\s*(?:junior|entry[- ]level|fresher|intern(?:ship)?)\b", role_title, re.I):
        return True
    if SENIOR_ROLE_PATTERN.search(role_title):
        return False
    return bool(ENTRY_LEVEL_ROLE_PATTERN.search(role_title))


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
        elif any(marker in lowered for marker in RESPONSIBILITY_MARKERS + BENEFIT_MARKERS):
            current_context = "keyword"

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
