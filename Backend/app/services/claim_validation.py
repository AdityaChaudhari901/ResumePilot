from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class ClaimCategory(StrEnum):
    metric = "metric"
    work_history = "work history"
    seniority = "seniority"
    credential = "certification or degree"
    scale = "user, customer, or revenue scale"
    production_reliability = "production, deployment, or reliability"


@dataclass(frozen=True, slots=True)
class UnsupportedClaim:
    category: ClaimCategory
    marker: str


CLAIM_TERMS: dict[ClaimCategory, frozenset[str]] = {
    ClaimCategory.work_history: frozenset(
        {
            "achieved",
            "award",
            "awarded",
            "employed",
            "founded",
            "patent",
            "patented",
            "served",
            "worked",
        }
    ),
    ClaimCategory.seniority: frozenset(
        {
            "director",
            "executive",
            "head",
            "leader",
            "leadership",
            "led",
            "managed",
            "manager",
            "principal",
            "senior",
            "staff",
        }
    ),
    ClaimCategory.credential: frozenset(
        {
            "bachelor",
            "bachelor's",
            "certificate",
            "certification",
            "certified",
            "degree",
            "diploma",
            "doctorate",
            "master's",
            "phd",
        }
    ),
    ClaimCategory.scale: frozenset(
        {
            "client",
            "clients",
            "customer",
            "customers",
            "enterprise",
            "revenue",
            "user",
            "users",
        }
    ),
    ClaimCategory.production_reliability: frozenset(
        {
            "availability",
            "deploy",
            "deployed",
            "deployment",
            "deployments",
            "production",
            "reliability",
            "reliable",
            "resilient",
            "sla",
            "uptime",
        }
    ),
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

ORGANIZATION_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z0-9&'.-]*(?:\s+[A-Z][A-Za-z0-9&'.-]*){0,4}\s+"
    r"(?:Corp(?:oration)?|Inc|LLC|Ltd|Limited|Labs?|Technologies|Systems|Solutions|Company|Co)\b"
)
WORK_ORGANIZATION_PATTERN = re.compile(
    r"\b(?i:worked|served|employed)\s+(?:(?i:as)\s+[^,.;]{1,80}\s+)?"
    r"(?i:at|for)\s+([A-Z][A-Za-z0-9&'.-]*(?:\s+[A-Z][A-Za-z0-9&'.-]*){0,4})"
)


def find_unsupported_claims(
    text: str,
    evidence_text: str,
    *,
    allowed_organizations: tuple[str, ...] = (),
) -> list[UnsupportedClaim]:
    """Return high-risk career claims that are absent from supporting evidence."""

    findings: list[UnsupportedClaim] = []
    for category, terms in CLAIM_TERMS.items():
        for term in sorted(terms):
            if _contains_term(text, term) and not _contains_term(evidence_text, term):
                findings.append(UnsupportedClaim(category=category, marker=term))

    for metric in _metric_claims(text):
        if _normalize(metric) not in _normalize(evidence_text):
            findings.append(UnsupportedClaim(category=ClaimCategory.metric, marker=metric))

    evidence_normalized = _normalize(evidence_text)
    allowed_normalized = {_normalize(value) for value in allowed_organizations if value.strip()}
    employment_organizations = {
        match.group(1).strip() for match in WORK_ORGANIZATION_PATTERN.finditer(text)
    }
    for organization in employment_organizations:
        if _normalize(organization) not in evidence_normalized:
            findings.append(
                UnsupportedClaim(category=ClaimCategory.work_history, marker=organization)
            )

    for organization in ORGANIZATION_PATTERN.findall(text):
        organization_normalized = _normalize(organization)
        if (
            organization_normalized in evidence_normalized
            or organization_normalized in allowed_normalized
        ):
            continue
        findings.append(UnsupportedClaim(category=ClaimCategory.work_history, marker=organization))

    return _dedupe_findings(findings)


def unsupported_claim_markers(text: str, evidence_text: str) -> list[str]:
    return [finding.marker for finding in find_unsupported_claims(text, evidence_text)]


def _contains_term(value: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", value, flags=re.IGNORECASE))


def _metric_claims(value: str) -> list[str]:
    claims: list[str] = []
    for pattern in METRIC_PATTERNS:
        for match in pattern.finditer(value):
            claim = match.group(0).strip()
            if claim and claim not in claims:
                claims.append(claim)
    return claims


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).casefold().strip()


def _dedupe_findings(findings: list[UnsupportedClaim]) -> list[UnsupportedClaim]:
    seen: set[tuple[ClaimCategory, str]] = set()
    deduped: list[UnsupportedClaim] = []
    for finding in findings:
        key = (finding.category, _normalize(finding.marker))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped
