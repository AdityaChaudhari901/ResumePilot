def test_upload_analyze_and_read_report(client, sample_resume_text, sample_job_text):
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", sample_resume_text.encode("utf-8"), "text/markdown")},
    )

    assert upload_response.status_code == 201
    resume_id = upload_response.json()["resume_id"]

    analyze_response = client.post(
        "/jobs/analyze",
        json={"resume_id": resume_id, "job_text": sample_job_text},
    )

    assert analyze_response.status_code == 200
    body = analyze_response.json()
    assert body["status"] == "completed"
    assert body["match_score"] >= 70

    report_response = client.get(f"/reports/{body['report_id']}")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["analysis_id"] == body["analysis_id"]
    assert report["tailored_bullets"]
    assert all(item["evidence_ids"] for item in report["tailored_bullets"])

    markdown_response = client.get(f"/reports/{body['report_id']}/markdown")
    assert markdown_response.status_code == 200
    assert "# Job Fit Report" in markdown_response.text
