from enum import StrEnum

from pydantic import Field, model_validator

from app.schemas.common import Confidence, StrictBaseModel


class MatchType(StrEnum):
    exact = "exact"
    synonym = "synonym"
    inferred = "inferred"


class ScoringVersion(StrEnum):
    legacy_unversioned = "legacy_unversioned"
    deterministic_v1 = "deterministic_v1"
    evidence_v2 = "evidence_v2"


class MatchScoreStatus(StrEnum):
    scored = "scored"
    provisional = "provisional"


class MatchScoreComponentStatus(StrEnum):
    scored = "scored"
    unknown = "unknown"
    not_applicable = "not_applicable"


class MatchScoreComponentKey(StrEnum):
    required_skills = "required_skills"
    responsibilities = "responsibilities"
    preferred_skills = "preferred_skills"
    experience = "experience"
    domain = "domain"
    evidence_strength = "evidence_strength"


EVIDENCE_V2_COMPONENT_WEIGHTS = {
    MatchScoreComponentKey.required_skills: 50.0,
    MatchScoreComponentKey.responsibilities: 20.0,
    MatchScoreComponentKey.preferred_skills: 10.0,
    MatchScoreComponentKey.experience: 15.0,
    MatchScoreComponentKey.domain: 5.0,
    MatchScoreComponentKey.evidence_strength: 0.0,
}


class MatchScoreComponent(StrictBaseModel):
    key: MatchScoreComponentKey
    status: MatchScoreComponentStatus
    score: float | None = Field(default=None, ge=0, le=100)
    base_weight: float = Field(ge=0, le=100)
    effective_weight: float = Field(ge=0, le=100)
    contribution: float = Field(ge=0, le=100)
    matched_count: int | None = Field(default=None, ge=0)
    total_count: int | None = Field(default=None, ge=0)
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_component_arithmetic(self) -> "MatchScoreComponent":
        if self.status == MatchScoreComponentStatus.scored:
            if self.score is None:
                raise ValueError("scored components require a numeric score")
            expected_contribution = round(self.score * self.effective_weight / 100, 2)
            if abs(expected_contribution - self.contribution) > 0.01:
                raise ValueError("component contribution does not match score and weight")
        elif self.status == MatchScoreComponentStatus.unknown:
            if self.score is not None or self.contribution != 0:
                raise ValueError("unknown components must reserve weight with zero contribution")
        elif self.score is not None or self.effective_weight != 0 or self.contribution != 0:
            raise ValueError("not-applicable components cannot contribute to the total")
        if self.matched_count is not None and self.total_count is None:
            raise ValueError("matched_count requires total_count")
        if (
            self.matched_count is not None
            and self.total_count is not None
            and self.matched_count > self.total_count
        ):
            raise ValueError("matched_count cannot exceed total_count")
        return self


def evidence_v2_effective_weights(
    components: list[MatchScoreComponent],
) -> dict[MatchScoreComponentKey, float]:
    by_key = {component.key: component for component in components}
    weighted = [
        by_key[key]
        for key in MatchScoreComponentKey
        if key in by_key
        and by_key[key].status != MatchScoreComponentStatus.not_applicable
        and by_key[key].base_weight > 0
    ]
    total_base_weight = sum(component.base_weight for component in weighted)
    effective: dict[MatchScoreComponentKey, float] = {}
    assigned_weight = 0.0
    for position, component in enumerate(weighted):
        if position == len(weighted) - 1:
            value = round(100.0 - assigned_weight, 2)
        else:
            value = round(component.base_weight / total_base_weight * 100, 2)
            assigned_weight += value
        effective[component.key] = value
    return effective


class MatchScoreBreakdown(StrictBaseModel):
    scoring_version: ScoringVersion
    score_kind: str = Field(
        default="deterministic_evidence_fit",
        pattern="^deterministic_evidence_fit$",
    )
    score_status: MatchScoreStatus
    uncapped_score: float = Field(ge=0, le=100)
    score_cap: float | None = Field(default=None, ge=0, le=100)
    total_score: float = Field(ge=0, le=100)
    components: list[MatchScoreComponent] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def validate_breakdown_arithmetic(self) -> "MatchScoreBreakdown":
        if self.scoring_version != ScoringVersion.evidence_v2:
            raise ValueError("score breakdowns are supported only for evidence_v2")
        if self.score_cap is not None and self.score_status != MatchScoreStatus.provisional:
            raise ValueError("capped score breakdowns must be provisional")
        keys = [component.key for component in self.components]
        if len(keys) != len(set(keys)) or set(keys) != set(MatchScoreComponentKey):
            raise ValueError("score breakdown must contain every component exactly once")
        for component in self.components:
            expected_base_weight = EVIDENCE_V2_COMPONENT_WEIGHTS[component.key]
            if component.base_weight != expected_base_weight:
                raise ValueError("score component base weight does not match evidence_v2")
        if (
            any(
                component.status == MatchScoreComponentStatus.unknown
                for component in self.components
            )
            and self.score_status != MatchScoreStatus.provisional
        ):
            raise ValueError("score breakdowns with unknown components must be provisional")
        base_weight = round(sum(component.base_weight for component in self.components), 2)
        if base_weight != 100:
            raise ValueError("score component base weights must total 100")
        expected_effective_weights = evidence_v2_effective_weights(self.components)
        for component in self.components:
            expected_effective_weight = expected_effective_weights.get(component.key, 0.0)
            if abs(component.effective_weight - expected_effective_weight) > 0.01:
                raise ValueError("score component effective weight is inconsistent")
        weighted_components = [
            component
            for component in self.components
            if component.status != MatchScoreComponentStatus.not_applicable
            and component.base_weight > 0
        ]
        effective_weight = round(
            sum(component.effective_weight for component in weighted_components),
            2,
        )
        if weighted_components and abs(effective_weight - 100) > 0.01:
            raise ValueError("weighted component effective weights must total 100")
        contribution = round(sum(component.contribution for component in self.components), 2)
        if abs(contribution - self.uncapped_score) > 0.01:
            raise ValueError("score component contributions do not reconcile")
        score_ceiling = self.score_cap if self.score_cap is not None else 100.0
        expected_total = min(self.uncapped_score, score_ceiling)
        if abs(expected_total - self.total_score) > 0.01:
            raise ValueError("total score does not reconcile with the configured cap")
        return self


class MatchedSkill(StrictBaseModel):
    skill: str = Field(min_length=1)
    match_type: MatchType
    resume_evidence_ids: list[str] = Field(min_length=1)
    job_evidence_text: str = Field(min_length=1)
    confidence: Confidence


class MissingSkill(StrictBaseModel):
    skill: str = Field(min_length=1)
    importance: str = Field(pattern="^(required|preferred)$")
    job_evidence_text: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)


class WeakSkill(StrictBaseModel):
    skill: str = Field(min_length=1)
    resume_evidence_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)


class MatchResult(StrictBaseModel):
    score: float = Field(ge=0, le=100)
    required_skill_score: float = Field(ge=0, le=100)
    preferred_skill_score: float = Field(ge=0, le=100)
    responsibility_alignment_score: float = Field(ge=0, le=100)
    experience_level_score: float = Field(ge=0, le=100)
    domain_keyword_score: float = Field(ge=0, le=100)
    resume_quality_score: float = Field(ge=0, le=100)
    matched_skills: list[MatchedSkill] = Field(default_factory=list)
    missing_skills: list[MissingSkill] = Field(default_factory=list)
    weak_skills: list[WeakSkill] = Field(default_factory=list)
    confidence: Confidence
    scoring_version: ScoringVersion = ScoringVersion.legacy_unversioned
    score_status: MatchScoreStatus = MatchScoreStatus.scored
    score_breakdown: MatchScoreBreakdown | None = None
