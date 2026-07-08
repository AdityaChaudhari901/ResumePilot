# 06 - Accuracy, Speed, and Reliability Plan

## Accuracy target

Do not claim 100 percent accuracy. The realistic engineering goal is:

```text
High precision for resume facts and required-skill matching.
Measurable recall for job requirements.
Zero tolerance for unsupported resume claims.
```

## Accuracy architecture

```text
Raw documents
  -> parsing
  -> normalization
  -> deterministic extraction
  -> structured LLM extraction
  -> merge and deduplicate
  -> evidence mapping
  -> deterministic match
  -> agent generation
  -> validation
  -> report
```

## Evidence-first design

Every important output must trace back to evidence.

| Output | Required evidence |
|---|---|
| Matched skill | Resume evidence + JD evidence |
| Missing skill | JD evidence + no resume evidence |
| Tailored bullet | Resume evidence |
| Cover letter claim | Resume evidence |
| Interview answer point | Resume evidence |
| ATS keyword suggestion | JD evidence |

## Confidence levels

### High confidence

- Exact or synonym skill match.
- Evidence appears in project/experience section.
- Job requirement explicitly says "required".

### Medium confidence

- Inferred related skill.
- Evidence appears only in skills list.
- JD wording is ambiguous.

### Low confidence

- Extracted from noisy PDF.
- Job page scraping incomplete.
- Skill appears only once with no context.
- Requirement is implied but not explicit.

## Matching accuracy techniques

### 1. Canonical skill dictionary

Maintain a local skill dictionary:

```json
{
  "javascript": ["js", "ecmascript"],
  "postgresql": ["postgres", "psql"],
  "fastapi": ["fast api"],
  "ci/cd": ["continuous integration", "continuous deployment"],
  "generative ai": ["genai", "llm applications"]
}
```

### 2. Skill taxonomy enrichment

Use public skill taxonomies for optional enrichment:

- O*NET for occupational data and skills.
- ESCO for multilingual skills, competences, knowledge, and occupations.

Do not rely only on taxonomy data because software job descriptions include fast-changing tools and product-specific terms.

### 3. Section-aware weighting

A skill in a project or work experience is stronger than a skill in a plain skills list.

Suggested weights:

```text
experience/project evidence: 1.0
certification evidence: 0.8
education evidence: 0.6
skills-list-only evidence: 0.4
```

### 4. Required vs preferred separation

A missing required skill matters more than a missing preferred skill.

### 5. Unsupported-claim detection

Use deterministic string checks plus optional LLM validation.

Reject generated claims if they include:

- technology absent from evidence
- company absent from evidence
- metric absent from evidence
- seniority absent from evidence
- certification absent from evidence
- production/deployment/users absent from evidence

## Evaluation metrics

### Extraction metrics

- JD required skill precision
- JD required skill recall
- resume skill precision
- resume skill recall
- section classification accuracy

### Matching metrics

- exact match correctness
- synonym match correctness
- inferred match correctness
- missing skill correctness
- false-positive skill rate

### Generation metrics

- unsupported claim rate
- bullet usefulness rating
- cover letter relevance rating
- interview question relevance rating
- JSON schema pass rate

### Reliability metrics

- API success rate
- average latency
- p95 latency
- workflow total latency
- per-step workflow latency
- rate-limit retry count
- failed scrape rate
- validation failure rate
- cost per analysis

## Speed plan

### Fast path

For pasted job descriptions:

1. skip browser scraping
2. parse with deterministic extractor
3. run only necessary agents
4. return report synchronously

Target: less than 15 seconds for normal text length.

### Slow path

For job URLs:

1. try Requests + BeautifulSoup
2. fallback to Playwright only if needed
3. cache fetched page by URL hash
4. queue long analysis

Target: less than 30 seconds for normal public job pages.

### Caching

Cache:

- resume parse by file hash
- job page by URL + content hash
- normalized skill dictionary
- completed analysis by resume version + JD hash
- embeddings by text hash

### Parallelization

Can run in parallel after matching:

- ATS bullet suggestions
- interview questions
- cover letter draft

But keep validation after all generation.

## Reliability plan

### Retries

Retry only safe, idempotent operations:

- LLM JSON parse failure
- transient network errors
- rate-limit errors
- worker crash

Do not retry:

- file upload duplicate writes without idempotency key
- external posting actions
- user confirmation actions

### Idempotency

Use hashes:

```text
resume_hash = sha256(file_bytes)
job_hash = sha256(clean_job_text)
analysis_key = sha256(resume_hash + job_hash + config_version)
```

### Queue design

Use background jobs when:

- job URL requires browser rendering
- resume file is large
- user requests full report with cover letter
- provider is rate limited

### Degraded mode

If LLM provider fails:

- return deterministic match report
- skip cover letter
- skip advanced interview prep
- show "LLM generation unavailable; deterministic analysis returned"

### Observability

Log for every analysis:

- request ID
- user/session ID
- resume ID
- job ID
- parsing latency
- matching latency
- LLM latency
- workflow trace total latency
- per-step workflow trace latency
- validation status
- token usage/cost if available
- errors

## Quality gates

Before returning a report:

- JSON schema valid.
- Required sections present.
- No unsupported claims.
- No hidden system prompts.
- No raw API keys.
- No external tool call performed without approval.
- Resume facts not exposed to other users.

## Benchmarks for portfolio

Create a test dataset:

```text
10 resumes x 20 job descriptions = 200 analysis pairs
```

Measure:

- skill precision
- unsupported-claim rate
- average latency
- manual usefulness score from 1-5
- number of edits needed before use

Portfolio claim after measurement:

```text
Evaluated on 200 resume/JD pairs and reduced unsupported generated claims to 0 in validation tests.
```

Only use numbers you actually measure.
