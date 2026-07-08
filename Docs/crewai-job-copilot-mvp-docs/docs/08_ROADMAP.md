# 08 - Roadmap and Milestones

## Phase 0 - Planning and data contracts

Duration: 1-2 days

Deliverables:

- product spec
- schemas for ResumeProfile, JobProfile, MatchResult, Report
- skill dictionary v1
- sample resumes and job descriptions
- evaluation checklist

Exit criteria:

- schemas reviewed
- scoring formula finalized
- unsupported-claim policy finalized

## Phase 1 - Backend foundation

Duration: 2-4 days

Features:

- FastAPI app
- SQLite database
- SQLAlchemy models
- resume upload endpoint
- report retrieval endpoints
- health endpoint
- environment config
- structured logging

Exit criteria:

- API boots locally
- Swagger UI works
- tests pass for health and upload

## Phase 2 - Resume ingestion

Duration: 3-5 days

Features:

- PDF/DOCX/TXT/MD extraction
- section classifier
- skill extractor
- resume fact IDs
- low-confidence warnings
- resume profile JSON

Exit criteria:

- sample resumes parsed
- skill extraction tests pass
- evidence IDs stable

## Phase 3 - Job ingestion

Duration: 3-5 days

Features:

- job URL fetcher
- pasted JD input
- job text cleaner
- job profile extractor
- robots/terms-aware behavior
- Playwright fallback
- cache by URL/content hash

Exit criteria:

- 10 sample job descriptions parsed
- blocked sites fall back to paste
- required/preferred split works

## Phase 4 - Deterministic matcher

Duration: 3-5 days

Features:

- skill normalization
- synonym dictionary
- exact/synonym/inferred matching
- weighted scoring
- missing skills
- weak skills
- evidence mapping

Exit criteria:

- same input produces same score
- false positives reviewed
- match report generated without LLM

## Phase 5 - CrewAI agent workflow

Duration: 4-7 days

Features:

- CrewAI Flow wrapper
- JD Parser Agent
- Resume Match Agent
- ATS Optimizer Agent
- Cover Letter Agent
- Interview Coach Agent
- Validation Gate
- structured outputs

Exit criteria:

- valid report JSON
- unsupported claims blocked
- report generated end-to-end

## Phase 6 - OpenClaw integration

Duration: 2-3 days

Features:

- OpenClaw `/job` skill
- local API token auth
- command parser
- default resume selection
- chat response formatting
- error responses

Exit criteria:

- `/job <url>` works
- `/job paste:<text>` works or equivalent
- unauthorized requests rejected

## Phase 7 - Reliability and performance

Duration: 3-5 days

Features:

- Redis queue
- worker
- retries with backoff
- caching
- idempotency keys
- degraded mode
- metrics

Exit criteria:

- long jobs queued
- duplicate analyses reuse cache
- provider failures return deterministic report

## Phase 8 - Web UI

Duration: 4-7 days

Features:

- dashboard
- resume upload
- job text input
- report viewer
- report export
- validation warnings

Exit criteria:

- non-technical user can run demo
- report is readable and exportable

## Phase 9 - Evaluation and portfolio polish

Duration: 3-5 days

Features:

- benchmark dataset
- eval script
- accuracy dashboard
- sample reports
- README screenshots
- demo video script

Exit criteria:

- measured metrics included
- resume bullet ready
- GitHub repo polished

## Suggested 4-week build plan

### Week 1

- finalize docs and schemas
- build FastAPI foundation
- implement resume parser

### Week 2

- implement job parser
- implement deterministic matcher
- generate basic report without agents

### Week 3

- add CrewAI agents
- add validation gate
- add OpenClaw `/job` integration

### Week 4

- add reliability, caching, tests
- run evals
- polish README and demo

## MVP feature release checklist

- [ ] Resume upload works.
- [ ] Resume parsing works.
- [ ] JD URL/paste works.
- [ ] Matching engine works.
- [ ] CrewAI agents generate report sections.
- [ ] Validator blocks unsupported claims.
- [ ] OpenClaw `/job` works.
- [ ] Reports saved to DB.
- [ ] Tests pass.
- [ ] README and demo ready.
