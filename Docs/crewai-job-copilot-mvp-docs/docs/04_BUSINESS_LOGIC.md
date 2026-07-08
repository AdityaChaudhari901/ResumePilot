# 04 - Business Logic

## Core business rule

The application is not allowed to optimize for sounding impressive at the cost of truth. It optimizes for:

1. truthful alignment,
2. clear gaps,
3. better wording,
4. measurable fit,
5. faster application preparation.

## Input types

### Resume input

Accepted formats:

- PDF
- DOCX
- TXT
- Markdown

Resume ingestion output:

- candidate identity
- contact fields
- skills
- experience
- projects
- education
- certifications
- raw facts with evidence IDs

### Job input

Accepted formats:

- public job URL
- pasted job description text
- optional company/role override

Job ingestion output:

- company
- role title
- location
- employment type
- required skills
- preferred skills
- responsibilities
- keywords
- experience requirements
- nice-to-have items
- red flags or unclear requirements

## Skill normalization

The matcher should normalize skills before comparing.

Examples:

| Raw text | Normalized skill |
|---|---|
| JS | JavaScript |
| TypeScript/TS | TypeScript |
| PostgreSQL/Postgres | PostgreSQL |
| REST APIs/RESTful APIs | REST API |
| CI/CD pipelines | CI/CD |
| LLM apps/GenAI apps | Generative AI |
| vector search/vector DB | Vector Search |

## Skill categories

Use categories to improve scoring and reporting:

- programming languages
- backend frameworks
- frontend frameworks
- databases
- cloud/devops
- AI/ML
- data tools
- testing
- security
- soft skills
- domain knowledge

## Matching strategy

### Exact match

Resume explicitly contains the same normalized skill.

Example:

- JD: Python
- Resume: Python

Result: strong match.

### Synonym match

Resume contains a known synonym.

Example:

- JD: Postgres
- Resume: PostgreSQL

Result: strong match.

### Evidence-backed inferred match

Resume contains related evidence but not the exact keyword.

Example:

- JD: REST API
- Resume: "Built FastAPI endpoints for authentication"

Result: partial match with explanation.

### Missing skill

No resume evidence exists.

Example:

- JD: Kubernetes
- Resume: no Kubernetes, container orchestration, Helm, or deployment evidence

Result: missing required skill.

### Weak skill

Skill appears only in a list, but no project/work evidence supports it.

Example:

- Resume skill list: Docker
- No project or experience mentions Docker

Result: weak match; suggest adding project evidence if true.

## Match score formula

MVP scoring formula:

```text
total_score =
  required_skill_score * 0.40 +
  responsibility_alignment_score * 0.20 +
  preferred_skill_score * 0.15 +
  experience_level_score * 0.10 +
  domain_keyword_score * 0.10 +
  resume_quality_score * 0.05
```

### Required skill score

```text
required_skill_score = matched_required_skills / total_required_skills * 100
```

Partial matches count as 0.5.

### Responsibility alignment score

Calculated from semantic alignment between job responsibilities and resume projects/experience.

Example:

- JD: "Build APIs for AI-powered workflows"
- Resume: "Built FastAPI API for multi-agent workflow orchestration"

Strong alignment.

### Preferred skill score

Preferred skills should not dominate the score. They are useful but less important than required skills.

### Experience level score

Rules:

- If JD asks 0-2 years and resume indicates fresher/junior: 100
- If JD asks 3-5 years and resume has only internship/project experience: 40-60
- If JD asks 5+ years and resume is fresher: 20-40
- If unclear: neutral 70

### Domain keyword score

Measures relevant terms:

- fintech
- healthcare
- SaaS
- DevOps
- GenAI
- security
- analytics

### Resume quality score

Measures whether the resume has:

- measurable outcomes
- action verbs
- project impact
- technical details
- links
- no unsupported claims

## Output decision logic

### Matched skills

Return skill only if there is resume evidence.

Each matched skill must include:

- skill name
- match type: exact/synonym/inferred
- resume evidence ID
- job evidence text
- confidence

### Missing skills

Return skill if:

- required by JD
- no resume evidence exists
- not a synonym or inferred match

Each missing skill includes:

- why it matters
- whether it is critical
- suggested learning/resource direction
- "do not add unless true" warning

### Tailored resume bullets

Allowed bullet types:

1. Rewrite existing bullet using better language.
2. Add JD keyword to existing truthful evidence.
3. Suggest optional bullet only if user confirms truth.

Rejected bullet types:

- fake company
- fake years of experience
- fake certification
- fake metrics
- fake production deployment
- fake leadership
- fake technology usage

## Example business logic

### Resume evidence

```text
project_03: Built a FastAPI backend with PostgreSQL and JWT authentication.
```

### Job requirement

```text
Required: Experience building REST APIs using Python.
```

### Valid tailored bullet

```text
Built Python-based REST API services using FastAPI, PostgreSQL, and JWT authentication for a secure backend project.
Evidence: project_03
```

### Invalid tailored bullet

```text
Led production deployment of enterprise REST APIs serving 1M users.
```

Reason: no evidence for leadership, production, enterprise, or 1M users.

## Report sections

Every report must contain:

1. Executive summary.
2. Match score.
3. Matched skills.
4. Missing/weak skills.
5. Resume bullet suggestions.
6. ATS keyword suggestions.
7. Cover letter draft.
8. Interview questions.
9. Validation warnings.
10. Next actions.

## Business KPIs

For portfolio/demo:

- average analysis time
- unsupported-claim block rate
- skill extraction precision
- skill extraction recall
- user rating for usefulness
- number of JD/resume pairs tested
- percentage of reports requiring manual correction

## Product differentiator

The differentiator is not "AI writes a cover letter". The differentiator is an evidence-backed application workflow:

```text
Resume evidence -> JD evidence -> deterministic match -> agent generation -> validation -> report
```
