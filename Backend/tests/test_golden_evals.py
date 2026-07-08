from scripts.run_golden_evals import run_golden_evals


def test_golden_eval_runner_generates_all_pairs(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.run_golden_evals.OUTPUT_DIR", tmp_path)

    summary = run_golden_evals()

    assert summary["resume_count"] >= 4
    assert summary["job_count"] >= 5
    assert summary["pair_count"] == summary["resume_count"] * summary["job_count"]
    assert summary["failed_pairs"] == []
    assert (tmp_path / "summary.json").exists()
