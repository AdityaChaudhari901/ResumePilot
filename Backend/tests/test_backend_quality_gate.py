from scripts.run_backend_quality_gate import (
    QualityThresholds,
    evaluate_backend_quality,
    quality_threshold_failures,
)


def test_backend_quality_gate_measures_golden_corpus(tmp_path):
    report = evaluate_backend_quality(
        output_path=tmp_path / "backend_quality_gate.json",
        thresholds=QualityThresholds(
            max_average_latency_ms=60_000,
            max_p95_latency_ms=60_000,
        ),
    )

    summary = report["summary"]

    assert report["passed"] is True
    assert summary["resume_count"] >= 4
    assert summary["job_count"] >= 5
    assert summary["pair_count"] == summary["resume_count"] * summary["job_count"]
    assert summary["schema_pass_rate"] == 1.0
    assert summary["evidence_gap_count"] == 0
    assert summary["unsupported_warning_count"] == 0
    assert summary["required_skill_routing_gap_count"] == 0
    assert summary["sensitive_output_hit_count"] == 0
    assert summary["average_latency_ms"] > 0
    assert summary["p95_latency_ms"] > 0
    assert (tmp_path / "backend_quality_gate.json").exists()


def test_quality_threshold_failures_explain_regressions():
    failures = quality_threshold_failures(
        {
            "schema_pass_rate": 0.95,
            "evidence_gap_count": 1,
            "unsupported_warning_count": 1,
            "required_skill_routing_gap_count": 1,
            "sensitive_output_hit_count": 1,
            "average_latency_ms": 501.0,
            "p95_latency_ms": 1501.0,
        },
        QualityThresholds(),
    )

    assert failures == [
        "schema_pass_rate 0.950 < 1.000",
        "evidence_gap_count 1 > 0",
        "unsupported_warning_count 1 > 0",
        "required_skill_routing_gap_count 1 > 0",
        "sensitive_output_hit_count 1 > 0",
        "average_latency_ms 501.00 > 500.00",
        "p95_latency_ms 1501.00 > 1500.00",
    ]
