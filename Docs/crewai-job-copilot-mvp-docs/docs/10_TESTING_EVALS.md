# 10 - Testing and Evaluation Plan

## Test layers

### Unit tests

- text cleaning
- resume parsing
- JD parsing
- skill normalization
- exact matching
- synonym matching
- score formula
- unsupported-claim detector

### Integration tests

- upload resume -> parse -> store
- analyze pasted JD -> report
- analyze job URL -> report
- export report Markdown, LaTeX, and PDF
- OpenClaw endpoint -> report
- invalid token -> 401
- report trace includes workflow mode, step statuses, and timing telemetry
- blocked scrape -> paste fallback message

### Agent tests

- output schema validation
- no unsupported claims
- required sections present
- malformed LLM output retry
- low-confidence field handling

### End-to-end tests

- sample resume + sample JD
- fresher resume + senior JD
- backend resume + frontend JD
- dashboard upload -> analyze -> export flow through Playwright
- AI resume + data analyst JD
- missing critical skill scenario

## Golden test set

Create a folder:

```text
evals/
  resumes/
    backend_fresher.md
    ai_engineer_junior.md
    frontend_junior.md
    data_analyst.md
  jobs/
    backend_python_junior.txt
    ai_platform_engineer.txt
    frontend_react.txt
    data_analyst_sql.txt
  expected/
    backend_python_junior.expected.json
```

## Manual review rubric

Score each report from 1-5:

| Criterion | Meaning |
|---|---|
| Skill match correctness | Did it correctly identify matched/missing skills? |
| Truthfulness | Did it avoid unsupported claims? |
| Resume usefulness | Are bullet suggestions actually usable? |
| JD relevance | Is output specific to the role? |
| Interview usefulness | Are questions likely and targeted? |
| Clarity | Is report easy to understand? |

## Automated eval checks

### Unsupported claim check

Input:

- generated bullet
- resume evidence facts

Output:

```json
{
  "supported": true,
  "unsupported_terms": [],
  "evidence_ids": ["project_01"]
}
```

### Skill false positive check

If matched skill has no evidence ID, fail.

### Missing required skill check

If JD says "required" and no evidence exists, it must appear in missing skills.

### Schema check

All reports must validate against `ApplicationReportSchema`.

## Regression testing

Every time prompts, models, or scoring rules change:

- run golden eval set
- run backend quality gate
- compare match scores
- compare unsupported-claim count
- compare JSON validity
- compare workflow trace timing shape
- compare workflow provider/token metadata shape
- compare latency and cost

Current backend command:

```bash
cd Backend
python scripts/run_backend_quality_gate.py
```

The gate measures the deterministic golden corpus for schema pass rate,
evidence gaps, unsupported claim warnings, required-skill routing gaps,
sensitive-output hits, average latency, and p95 latency. The generated JSON
report is written to `Backend/evals/outputs/backend_quality_gate.json`, which is
ignored by git.

Current frontend browser smoke command:

```bash
cd Frontend
npm run test:e2e:install
npm run test:e2e
```

The Playwright smoke starts FastAPI and the production Next.js server, uploads a
sample resume, analyzes the sample job, verifies workflow trace timing,
Markdown/LaTeX/PDF exports, and captures desktop/mobile screenshots in ignored
local artifacts.

## Demo dataset plan

Minimum useful demo dataset:

```text
5 sample resumes
20 sample job descriptions
100 analysis pairs
```

Better portfolio dataset:

```text
10 sample resumes
20 job descriptions
200 analysis pairs
```

## Metrics to show in README

Only after measurement:

```text
- Evaluated on 200 resume/JD pairs.
- 0 unsupported generated claims after validation.
- 95 percent JSON schema pass rate before retry.
- Average analysis latency: X seconds.
- Required-skill extraction precision: X percent.
```

Do not invent these metrics. Measure them first.

## CI checklist

- run pytest
- run ruff/formatting if configured
- run type checks if configured
- run sample analysis
- verify report export endpoints
- run Playwright dashboard smoke
- run backend quality gate
- validate generated report JSON
- fail build if unsupported claim detector fails
