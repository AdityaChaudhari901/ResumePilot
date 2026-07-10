from __future__ import annotations

import argparse
import json
import math
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.schemas.agent import AgentWorkflowMode
from app.schemas.common import ValidationWarning
from app.schemas.job import JobProfile
from app.schemas.report import ApplicationReport
from app.schemas.resume import ResumeProfile
from app.services.agent_workflow import run_application_agent_workflow
from app.services.job_parser import parse_job_profile
from app.services.matcher import match_resume_to_job
from app.services.resume_parser import parse_resume_profile
from app.services.validator import validate_report_against_resume

BACKEND_ROOT = Path(__file__).resolve().parents[1]
EVALS_ROOT = BACKEND_ROOT / "evals"
RESUME_DIR = EVALS_ROOT / "resumes"
JOB_DIR = EVALS_ROOT / "jobs"
OUTPUT_DIR = EVALS_ROOT / "outputs"
DEFAULT_OUTPUT_PATH = OUTPUT_DIR / "backend_quality_gate.json"
MATCH_SCORE_CASES_PATH = EVALS_ROOT / "match_score_cases.json"

EVIDENCE_GAP_WARNING_CODES = frozenset(
    {
        "matched_skill_missing_evidence",
        "bullet_missing_evidence",
        "supported_keyword_missing_evidence",
        "interview_answer_missing_evidence",
    }
)
UNSUPPORTED_WARNING_CODES = frozenset(
    {"bullet_has_unsupported_skill", "cover_letter_has_unsupported_skill"}
)
SENSITIVE_OUTPUT_PATTERN = re.compile(
    r"\b(api[_ -]?key|secret[_ -]?key|system prompt|developer message)\b"
    r"|\bbearer\s+[a-z0-9._-]{10,}",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class QualityThresholds:
    min_schema_pass_rate: float = 1.0
    max_evidence_gap_count: int = 0
    max_unsupported_warning_count: int = 0
    max_required_skill_routing_gap_count: int = 0
    max_sensitive_output_hit_count: int = 0
    max_score_benchmark_failure_count: int = 0
    max_average_latency_ms: float = 500.0
    max_p95_latency_ms: float = 1500.0


def evaluate_backend_quality(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    thresholds: QualityThresholds = QualityThresholds(),
) -> dict[str, Any]:
    """Evaluate deterministic backend speed and accuracy on the golden corpus."""

    resume_paths = sorted(RESUME_DIR.glob("*.md"))
    job_paths = sorted(JOB_DIR.glob("*.txt"))
    pairs: list[dict[str, Any]] = []
    latencies_ms: list[float] = []
    settings = Settings(
        APP_ENV="quality-gate",
        AGENT_WORKFLOW_MODE=AgentWorkflowMode.deterministic_fallback,
    )

    analysis_id = 1
    for resume_index, resume_path in enumerate(resume_paths, start=1):
        for job_index, job_path in enumerate(job_paths, start=1):
            pair = _evaluate_pair(
                analysis_id=analysis_id,
                resume_id=resume_index,
                job_id=job_index,
                resume_path=resume_path,
                job_path=job_path,
                settings=settings,
            )
            pairs.append(pair)
            latencies_ms.append(pair["latency_ms"])
            analysis_id += 1

    summary = _build_summary(
        resume_count=len(resume_paths),
        job_count=len(job_paths),
        pairs=pairs,
        latencies_ms=latencies_ms,
    )
    score_benchmark = _evaluate_match_score_benchmark()
    summary.update(
        {
            "score_benchmark_case_count": score_benchmark["case_count"],
            "score_benchmark_failure_count": score_benchmark["failure_count"],
            "score_benchmark_failures": score_benchmark["failures"],
        }
    )
    threshold_failures = quality_threshold_failures(summary, thresholds)
    report = {
        "gate": "backend_quality",
        "workflow_mode": AgentWorkflowMode.deterministic_fallback,
        "thresholds": asdict(thresholds),
        "passed": not threshold_failures,
        "threshold_failures": threshold_failures,
        "summary": summary,
        "score_benchmark": score_benchmark,
        "pairs": pairs,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def quality_threshold_failures(
    summary: dict[str, Any],
    thresholds: QualityThresholds,
) -> list[str]:
    failures: list[str] = []

    if summary["schema_pass_rate"] < thresholds.min_schema_pass_rate:
        failures.append(
            "schema_pass_rate "
            f"{summary['schema_pass_rate']:.3f} < {thresholds.min_schema_pass_rate:.3f}"
        )
    if summary["evidence_gap_count"] > thresholds.max_evidence_gap_count:
        failures.append(
            "evidence_gap_count "
            f"{summary['evidence_gap_count']} > {thresholds.max_evidence_gap_count}"
        )
    if summary["unsupported_warning_count"] > thresholds.max_unsupported_warning_count:
        failures.append(
            "unsupported_warning_count "
            f"{summary['unsupported_warning_count']} > "
            f"{thresholds.max_unsupported_warning_count}"
        )
    if (
        summary["required_skill_routing_gap_count"]
        > thresholds.max_required_skill_routing_gap_count
    ):
        failures.append(
            "required_skill_routing_gap_count "
            f"{summary['required_skill_routing_gap_count']} > "
            f"{thresholds.max_required_skill_routing_gap_count}"
        )
    if summary["sensitive_output_hit_count"] > thresholds.max_sensitive_output_hit_count:
        failures.append(
            "sensitive_output_hit_count "
            f"{summary['sensitive_output_hit_count']} > "
            f"{thresholds.max_sensitive_output_hit_count}"
        )
    if summary["score_benchmark_failure_count"] > thresholds.max_score_benchmark_failure_count:
        failures.append(
            "score_benchmark_failure_count "
            f"{summary['score_benchmark_failure_count']} > "
            f"{thresholds.max_score_benchmark_failure_count}"
        )
    if summary["average_latency_ms"] > thresholds.max_average_latency_ms:
        failures.append(
            "average_latency_ms "
            f"{summary['average_latency_ms']:.2f} > {thresholds.max_average_latency_ms:.2f}"
        )
    if summary["p95_latency_ms"] > thresholds.max_p95_latency_ms:
        failures.append(
            f"p95_latency_ms {summary['p95_latency_ms']:.2f} > {thresholds.max_p95_latency_ms:.2f}"
        )

    return failures


def _evaluate_pair(
    *,
    analysis_id: int,
    resume_id: int,
    job_id: int,
    resume_path: Path,
    job_path: Path,
    settings: Settings,
) -> dict[str, Any]:
    pair_name = f"{resume_path.stem}__{job_path.stem}"
    started_at = time.perf_counter()

    resume = parse_resume_profile(resume_path.read_text(encoding="utf-8"), resume_id=resume_id)
    job = parse_job_profile(job_path.read_text(encoding="utf-8"), job_id=job_id)
    match = match_resume_to_job(resume, job)
    workflow = run_application_agent_workflow(
        analysis_id=analysis_id,
        resume=resume,
        job=job,
        match=match,
        settings=settings,
    )
    latency_ms = (time.perf_counter() - started_at) * 1000

    report = workflow.report
    schema_error: str | None = None
    try:
        ApplicationReport.model_validate_json(report.model_dump_json())
    except Exception as exc:  # pragma: no cover - exercised only on schema regressions.
        schema_error = str(exc)

    validation_warnings = _dedupe_warnings(
        [*report.validation_warnings, *validate_report_against_resume(report, resume)]
    )
    warning_codes = [warning.code for warning in validation_warnings]
    required_skill_routing_gaps = _required_skill_routing_gaps(job, report)
    sensitive_hits = _sensitive_output_hits(report)
    evidence_gap_count = _evidence_gap_count(report, resume, validation_warnings)
    unsupported_warning_count = _unsupported_warning_count(report, validation_warnings)

    return {
        "pair": pair_name,
        "resume": resume_path.name,
        "job": job_path.name,
        "schema_valid": schema_error is None,
        "schema_error": schema_error,
        "latency_ms": round(latency_ms, 2),
        "match_score": match.score,
        "matched_skill_count": len(report.matched_skills),
        "missing_skill_count": len(report.missing_skills),
        "validation_warning_codes": warning_codes,
        "evidence_gap_count": evidence_gap_count,
        "unsupported_warning_count": unsupported_warning_count,
        "required_skill_routing_gaps": required_skill_routing_gaps,
        "sensitive_output_hits": sensitive_hits,
        "workflow_trace_steps": [step.name for step in workflow.trace.steps],
    }


def _build_summary(
    *,
    resume_count: int,
    job_count: int,
    pairs: list[dict[str, Any]],
    latencies_ms: list[float],
) -> dict[str, Any]:
    pair_count = len(pairs)
    schema_pass_count = sum(1 for pair in pairs if pair["schema_valid"])
    evidence_gap_count = sum(pair["evidence_gap_count"] for pair in pairs)
    unsupported_warning_count = sum(pair["unsupported_warning_count"] for pair in pairs)
    required_skill_routing_gap_count = sum(
        len(pair["required_skill_routing_gaps"]) for pair in pairs
    )
    sensitive_output_hit_count = sum(len(pair["sensitive_output_hits"]) for pair in pairs)
    failed_pairs = [
        pair["pair"]
        for pair in pairs
        if (
            not pair["schema_valid"]
            or pair["evidence_gap_count"]
            or pair["unsupported_warning_count"]
            or pair["required_skill_routing_gaps"]
            or pair["sensitive_output_hits"]
        )
    ]

    return {
        "resume_count": resume_count,
        "job_count": job_count,
        "pair_count": pair_count,
        "schema_pass_count": schema_pass_count,
        "schema_pass_rate": round(schema_pass_count / pair_count, 4) if pair_count else 0.0,
        "evidence_gap_count": evidence_gap_count,
        "unsupported_warning_count": unsupported_warning_count,
        "required_skill_routing_gap_count": required_skill_routing_gap_count,
        "sensitive_output_hit_count": sensitive_output_hit_count,
        "average_latency_ms": round(sum(latencies_ms) / len(latencies_ms), 2)
        if latencies_ms
        else 0.0,
        "p95_latency_ms": round(_nearest_rank_percentile(latencies_ms, 95), 2),
        "max_latency_ms": round(max(latencies_ms), 2) if latencies_ms else 0.0,
        "failed_pairs": failed_pairs,
    }


def _evaluate_match_score_benchmark() -> dict[str, Any]:
    corpus = json.loads(MATCH_SCORE_CASES_PATH.read_text(encoding="utf-8"))
    expected_version = str(corpus["scoring_version"])
    failures: list[str] = []
    results: dict[str, dict[str, Any]] = {}

    for index, case in enumerate(corpus["cases"], start=1):
        case_id = str(case["id"])
        resume = parse_resume_profile(str(case["resume_text"]), resume_id=index)
        job = parse_job_profile(str(case["job_text"]), job_id=index)
        match = match_resume_to_job(resume, job)
        breakdown = match.score_breakdown
        case_failures: list[str] = []
        if match.scoring_version.value != expected_version:
            case_failures.append(f"version {match.scoring_version.value} != {expected_version}")
        if breakdown is None:
            case_failures.append("score breakdown missing")
            components: dict[str, Any] = {}
        else:
            components = {component.key.value: component for component in breakdown.components}
            contribution = round(
                sum(component.contribution for component in breakdown.components),
                2,
            )
            if contribution != breakdown.uncapped_score:
                case_failures.append("component contributions do not reconcile")
            if breakdown.total_score != match.score:
                case_failures.append("breakdown total does not match result score")

        _append_band_failure(
            case_failures,
            label="total score",
            actual=match.score,
            score_band=case["score_band"],
        )
        for component_key, expectation in case.get("components", {}).items():
            component = components.get(component_key)
            if component is None:
                case_failures.append(f"component {component_key} missing")
                continue
            expected_status = str(expectation["status"])
            if component.status.value != expected_status:
                case_failures.append(
                    f"component {component_key} status {component.status.value} "
                    f"!= {expected_status}"
                )
            if component.score is not None:
                _append_band_failure(
                    case_failures,
                    label=f"component {component_key}",
                    actual=component.score,
                    score_band=expectation["score_band"],
                )
        failures.extend(f"{case_id}: {failure}" for failure in case_failures)
        results[case_id] = {
            "score": match.score,
            "score_status": match.score_status.value,
            "failures": case_failures,
        }

    for expectation in corpus.get("pairwise_expectations", []):
        higher_id = str(expectation["higher"])
        lower_id = str(expectation["lower"])
        minimum_delta = float(expectation["minimum_delta"])
        actual_delta = round(results[higher_id]["score"] - results[lower_id]["score"], 2)
        if actual_delta < minimum_delta:
            failures.append(
                f"pairwise {higher_id} > {lower_id}: delta {actual_delta} < {minimum_delta}"
            )

    return {
        "schema_version": corpus["schema_version"],
        "scoring_version": expected_version,
        "case_count": len(results),
        "failure_count": len(failures),
        "failures": failures,
        "results": results,
    }


def _append_band_failure(
    failures: list[str],
    *,
    label: str,
    actual: float,
    score_band: list[float],
) -> None:
    minimum, maximum = (float(value) for value in score_band)
    if not minimum <= actual <= maximum:
        failures.append(f"{label} {actual} outside [{minimum}, {maximum}]")


def _required_skill_routing_gaps(
    job: JobProfile,
    report: ApplicationReport,
) -> list[str]:
    required_skill_names = {_normalize_skill(skill.name) for skill in job.required_skills}
    matched_skill_names = {_normalize_skill(skill.skill) for skill in report.matched_skills}
    missing_required_skill_names = {
        _normalize_skill(skill.skill)
        for skill in report.missing_skills
        if skill.importance == "required"
    }
    routed_skill_names = matched_skill_names | missing_required_skill_names
    return sorted(skill for skill in required_skill_names if skill not in routed_skill_names)


def _evidence_gap_count(
    report: ApplicationReport,
    resume: ResumeProfile,
    validation_warnings: list[ValidationWarning],
) -> int:
    facts_by_id = {fact.id for fact in resume.facts}
    gap_count = sum(
        1 for warning in validation_warnings if warning.code in EVIDENCE_GAP_WARNING_CODES
    )
    gap_count += sum(
        1
        for matched in report.matched_skills
        for evidence_id in matched.resume_evidence_ids
        if evidence_id not in facts_by_id
    )
    gap_count += sum(
        1
        for bullet in report.tailored_bullets
        for evidence_id in bullet.evidence_ids
        if evidence_id not in facts_by_id
    )
    gap_count += sum(
        1
        for keyword in report.ats_keywords
        if keyword.status == "supported" and not keyword.evidence_ids
    )
    gap_count += sum(
        1
        for group in report.interview_questions
        for evidence_id in group.suggested_answer_evidence_ids
        if evidence_id not in facts_by_id
    )
    return gap_count


def _unsupported_warning_count(
    report: ApplicationReport,
    validation_warnings: list[ValidationWarning],
) -> int:
    return sum(
        1 for warning in validation_warnings if warning.code in UNSUPPORTED_WARNING_CODES
    ) + sum(len(bullet.unsupported_claims) for bullet in report.tailored_bullets)


def _sensitive_output_hits(report: ApplicationReport) -> list[str]:
    payload = report.model_dump_json()
    return sorted({match.group(0) for match in SENSITIVE_OUTPUT_PATTERN.finditer(payload)})


def _dedupe_warnings(warnings: list[ValidationWarning]) -> list[ValidationWarning]:
    deduped: list[ValidationWarning] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for warning in warnings:
        key = (warning.code, warning.message, tuple(warning.evidence_ids))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(warning)
    return deduped


def _normalize_skill(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _nearest_rank_percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile / 100 * len(ordered)))
    return ordered[rank - 1]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic backend speed and accuracy quality gates."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--min-schema-pass-rate", type=float, default=1.0)
    parser.add_argument("--max-evidence-gap-count", type=int, default=0)
    parser.add_argument("--max-unsupported-warning-count", type=int, default=0)
    parser.add_argument("--max-required-skill-routing-gap-count", type=int, default=0)
    parser.add_argument("--max-sensitive-output-hit-count", type=int, default=0)
    parser.add_argument("--max-score-benchmark-failure-count", type=int, default=0)
    parser.add_argument("--max-average-latency-ms", type=float, default=500.0)
    parser.add_argument("--max-p95-latency-ms", type=float, default=1500.0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    thresholds = QualityThresholds(
        min_schema_pass_rate=args.min_schema_pass_rate,
        max_evidence_gap_count=args.max_evidence_gap_count,
        max_unsupported_warning_count=args.max_unsupported_warning_count,
        max_required_skill_routing_gap_count=args.max_required_skill_routing_gap_count,
        max_sensitive_output_hit_count=args.max_sensitive_output_hit_count,
        max_score_benchmark_failure_count=args.max_score_benchmark_failure_count,
        max_average_latency_ms=args.max_average_latency_ms,
        max_p95_latency_ms=args.max_p95_latency_ms,
    )
    report = evaluate_backend_quality(output_path=args.output, thresholds=thresholds)
    summary = report["summary"]
    print(
        "Backend quality gate "
        f"{'passed' if report['passed'] else 'failed'}: "
        f"{summary['pair_count']} pairs, "
        f"schema pass {summary['schema_pass_rate']:.0%}, "
        f"evidence gaps {summary['evidence_gap_count']}, "
        f"unsupported warnings {summary['unsupported_warning_count']}, "
        f"required-skill routing gaps {summary['required_skill_routing_gap_count']}, "
        f"score benchmark failures {summary['score_benchmark_failure_count']}, "
        f"avg {summary['average_latency_ms']:.2f} ms, "
        f"p95 {summary['p95_latency_ms']:.2f} ms."
    )
    if report["threshold_failures"]:
        raise SystemExit("Quality gate failures: " + "; ".join(report["threshold_failures"]))


if __name__ == "__main__":
    main()
