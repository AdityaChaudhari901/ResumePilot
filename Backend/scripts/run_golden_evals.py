from __future__ import annotations

import json
from pathlib import Path

from app.services.job_parser import parse_job_profile
from app.services.matcher import match_resume_to_job
from app.services.report_generator import generate_report, report_to_markdown
from app.services.resume_parser import parse_resume_profile
from app.services.validator import validate_report_against_resume

BACKEND_ROOT = Path(__file__).resolve().parents[1]
EVALS_ROOT = BACKEND_ROOT / "evals"
RESUME_DIR = EVALS_ROOT / "resumes"
JOB_DIR = EVALS_ROOT / "jobs"
OUTPUT_DIR = EVALS_ROOT / "outputs"


def run_golden_evals() -> dict[str, object]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs: list[dict[str, object]] = []
    failures: list[str] = []

    analysis_id = 1
    for resume_index, resume_path in enumerate(sorted(RESUME_DIR.glob("*.md")), start=1):
        resume = parse_resume_profile(
            resume_path.read_text(encoding="utf-8"), resume_id=resume_index
        )
        for job_index, job_path in enumerate(sorted(JOB_DIR.glob("*.txt")), start=1):
            job = parse_job_profile(job_path.read_text(encoding="utf-8"), job_id=job_index)
            match = match_resume_to_job(resume, job)
            report = generate_report(
                analysis_id=analysis_id,
                resume=resume,
                job=job,
                match=match,
                validation_warnings=[],
            )
            validation_warnings = validate_report_against_resume(report, resume)
            report.validation_warnings.extend(validation_warnings)
            pair_name = f"{resume_path.stem}__{job_path.stem}"
            pair_dir = OUTPUT_DIR / pair_name
            pair_dir.mkdir(parents=True, exist_ok=True)
            (pair_dir / "report.json").write_text(
                json.dumps(report.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )
            (pair_dir / "report.md").write_text(report_to_markdown(report), encoding="utf-8")

            if any(warning.code.endswith("missing_evidence") for warning in validation_warnings):
                failures.append(pair_name)

            pairs.append(
                {
                    "pair": pair_name,
                    "resume": resume_path.name,
                    "job": job_path.name,
                    "match_score": match.score,
                    "matched_skills": [skill.skill for skill in match.matched_skills],
                    "missing_skills": [skill.skill for skill in match.missing_skills],
                    "validation_warning_count": len(report.validation_warnings),
                }
            )
            analysis_id += 1

    summary = {
        "resume_count": len(list(RESUME_DIR.glob("*.md"))),
        "job_count": len(list(JOB_DIR.glob("*.txt"))),
        "pair_count": len(pairs),
        "failed_pairs": failures,
        "pairs": pairs,
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    summary = run_golden_evals()
    print(
        f"Evaluated {summary['pair_count']} pairs "
        f"({summary['resume_count']} resumes x {summary['job_count']} jobs)."
    )
    if summary["failed_pairs"]:
        raise SystemExit(f"Validation failures: {summary['failed_pairs']}")


if __name__ == "__main__":
    main()
