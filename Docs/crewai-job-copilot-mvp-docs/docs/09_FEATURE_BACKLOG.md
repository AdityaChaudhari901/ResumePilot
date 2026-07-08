# 09 - Feature Backlog

## P0 - Must have for MVP

| Feature | Description |
|---|---|
| Resume upload | Upload PDF/DOCX/TXT/MD resume. |
| Resume parser | Extract structured profile and evidence IDs. |
| JD input | Accept job URL or pasted JD text. |
| JD parser | Extract required/preferred skills and responsibilities. |
| Skill matcher | Deterministic score and matched/missing skills. |
| Report generator | JSON + Markdown report. |
| ATS suggestions | Evidence-backed bullet rewrites and keywords. |
| Cover letter draft | Concise draft using validated facts. |
| Interview questions | Role-specific prep questions. |
| Validation gate | Blocks unsupported claims. |
| OpenClaw `/job` | Chat command integration. |
| Basic auth | API token for OpenClaw endpoint. |
| Tests | Unit tests for parsing/matching/validation. |

## P1 - Strong portfolio upgrades

| Feature | Description |
|---|---|
| Web dashboard | Upload resume and view reports. |
| Multiple resumes | Maintain variants: backend, frontend, AI, data. |
| Skill gap planner | Suggest 7-day or 30-day learning plan. |
| Report export | Export Markdown, PDF, DOCX. |
| Job tracker | Track applied/saved/interview status. |
| Email draft | Draft recruiter email with approval. |
| Vector search | Semantic matching with embeddings. |
| Observability | Tracing, metrics, cost logs. |
| Benchmark evals | Accuracy dataset and scoring script. |

## P2 - Advanced features

| Feature | Description |
|---|---|
| Browser extension | Analyze jobs directly on job pages. |
| Resume versioning | Compare bullet variants. |
| A/B resume suggestions | Generate multiple tailored versions. |
| Calendar integration | Interview prep reminders. |
| Gmail integration | Parse recruiter emails with consent. |
| Job board integrations | LinkedIn/Indeed/Naukri manual import or compliant APIs. |
| Multi-user mode | Auth, RBAC, data isolation. |
| Team mode | Placement-cell or coaching dashboard. |
| Fine-grained eval dashboard | Per-agent performance tracking. |

## Nice-to-have commands

```text
/job <url>
/job paste <text>
/match <job_id>
/cover <job_id>
/interview <job_id>
/resume status
/resume set-default <resume_id>
/report <report_id>
/delete resume <resume_id>
```

## Report template

```markdown
# Job Fit Report

## 1. Executive Summary
...

## 2. Match Score
...

## 3. Matched Skills
...

## 4. Missing or Weak Skills
...

## 5. Tailored Resume Bullet Suggestions
...

## 6. ATS Keyword Suggestions
...

## 7. Cover Letter Draft
...

## 8. Interview Preparation
...

## 9. Validation Warnings
...

## 10. Next Actions
...
```
