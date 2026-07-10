from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.db.models import AnalysisRecord
from app.schemas.match import (
    MatchResult,
    MatchScoreBreakdown,
    MatchScoreStatus,
    ScoringVersion,
)
from app.schemas.report import ApplicationReport

SCORE_EXTENSION_FIELDS = {"scoring_version", "score_status", "score_breakdown"}


class ScoreContractInvariantError(RuntimeError):
    """A persisted or generated score contract cannot be repaired by retrying."""


def executable_scoring_version(value: str | ScoringVersion | None) -> ScoringVersion:
    raw_version = value or ScoringVersion.deterministic_v1
    try:
        version = ScoringVersion(raw_version)
    except ValueError as exc:
        raise ScoreContractInvariantError(
            "Workflow references an unsupported scoring version"
        ) from exc
    if version == ScoringVersion.legacy_unversioned:
        return ScoringVersion.deterministic_v1
    return version


def stage_analysis_score_contract(
    analysis: AnalysisRecord,
    match: MatchResult,
) -> None:
    _validate_match_contract(match)
    analysis.scoring_version = match.scoring_version.value
    analysis.score_status = match.score_status.value
    analysis.score_breakdown_json = (
        match.score_breakdown.model_dump(mode="json") if match.score_breakdown else None
    )


def persisted_match_payload(match: MatchResult) -> dict[str, Any]:
    """Keep business JSON readable by the pre-versioning rollback binary."""

    return match.model_dump(mode="json", exclude=SCORE_EXTENSION_FIELDS)


def persisted_report_payload(report: ApplicationReport) -> dict[str, Any]:
    """Keep business JSON readable by the pre-versioning rollback binary."""

    return report.model_dump(mode="json", exclude=SCORE_EXTENSION_FIELDS)


def hydrate_match_score_contract(
    analysis: AnalysisRecord,
    match: MatchResult,
) -> MatchResult:
    version, score_status, breakdown = score_contract_from_analysis(analysis)
    hydrated = MatchResult.model_validate(
        {
            **match.model_dump(mode="json", exclude=SCORE_EXTENSION_FIELDS),
            "scoring_version": version,
            "score_status": score_status,
            "score_breakdown": breakdown.model_dump(mode="json") if breakdown else None,
        }
    )
    _validate_match_contract(hydrated)
    if abs(analysis.match_score - hydrated.score) > 0.01:
        raise ScoreContractInvariantError("Analysis and match-result scores are inconsistent")
    return hydrated


def hydrate_report_score_contract(
    analysis: AnalysisRecord,
    report: ApplicationReport,
) -> ApplicationReport:
    version, score_status, breakdown = score_contract_from_analysis(analysis)
    hydrated = ApplicationReport.model_validate(
        {
            **report.model_dump(mode="json", exclude=SCORE_EXTENSION_FIELDS),
            "scoring_version": version,
            "score_status": score_status,
            "score_breakdown": breakdown.model_dump(mode="json") if breakdown else None,
        }
    )
    validate_report_score_contract(analysis, hydrated)
    return hydrated


def score_contract_from_analysis(
    analysis: AnalysisRecord,
) -> tuple[ScoringVersion, MatchScoreStatus, MatchScoreBreakdown | None]:
    try:
        version = ScoringVersion(analysis.scoring_version or ScoringVersion.legacy_unversioned)
        score_status = MatchScoreStatus(analysis.score_status or MatchScoreStatus.scored)
        breakdown = (
            MatchScoreBreakdown.model_validate(analysis.score_breakdown_json)
            if analysis.score_breakdown_json
            else None
        )
    except (ValueError, ValidationError) as exc:
        raise ScoreContractInvariantError("Persisted analysis score metadata is invalid") from exc
    if version == ScoringVersion.evidence_v2 and breakdown is None:
        raise ScoreContractInvariantError("Evidence v2 analysis is missing its score breakdown")
    if version != ScoringVersion.evidence_v2 and breakdown is not None:
        raise ScoreContractInvariantError(
            "Legacy analysis cannot carry an evidence v2 score breakdown"
        )
    if breakdown is not None:
        if breakdown.scoring_version != version:
            raise ScoreContractInvariantError(
                "Persisted score breakdown version does not match the analysis"
            )
        if breakdown.score_status != score_status:
            raise ScoreContractInvariantError(
                "Persisted score breakdown status does not match the analysis"
            )
        if abs(breakdown.total_score - analysis.match_score) > 0.01:
            raise ScoreContractInvariantError(
                "Persisted score breakdown total does not match the analysis"
            )
    return version, score_status, breakdown


def validate_report_score_contract(
    analysis: AnalysisRecord,
    report: ApplicationReport,
) -> None:
    version, score_status, breakdown = score_contract_from_analysis(analysis)
    if abs(analysis.match_score - report.match_score) > 0.01:
        raise ScoreContractInvariantError("Analysis and report match scores are inconsistent")
    if report.scoring_version != version or report.score_status != score_status:
        raise ScoreContractInvariantError("Analysis and report score metadata are inconsistent")
    if report.score_breakdown != breakdown:
        raise ScoreContractInvariantError("Analysis and report score breakdowns are inconsistent")


def _validate_match_contract(match: MatchResult) -> None:
    breakdown = match.score_breakdown
    if match.scoring_version == ScoringVersion.evidence_v2 and breakdown is None:
        raise ScoreContractInvariantError("Evidence v2 match result requires a score breakdown")
    if match.scoring_version != ScoringVersion.evidence_v2 and breakdown is not None:
        raise ScoreContractInvariantError(
            "Legacy match results cannot carry an evidence v2 score breakdown"
        )
    if breakdown is None:
        return
    if breakdown.scoring_version != match.scoring_version:
        raise ScoreContractInvariantError("Match score breakdown version is inconsistent")
    if breakdown.score_status != match.score_status:
        raise ScoreContractInvariantError("Match score breakdown status is inconsistent")
    if abs(breakdown.total_score - match.score) > 0.01:
        raise ScoreContractInvariantError("Match score breakdown total is inconsistent")
