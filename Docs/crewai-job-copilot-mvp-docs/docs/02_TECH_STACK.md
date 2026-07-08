# 02 - Tech Stack Decision

## Recommended MVP stack

| Layer | Technology | Why |
|---|---|---|
| Chat gateway | OpenClaw | Slash command interface for `/job`, local/private ChatOps style workflow. |
| Agent orchestration | CrewAI | Role-based agents plus Flows for controlled sequential execution. |
| Backend API | FastAPI | High-performance Python API with type hints and automatic OpenAPI docs. |
| Data validation | Pydantic v2 | Strict request/response schemas and structured agent outputs. |
| Database - MVP | SQLite | Simple local development and demo. |
| Database - V1 | PostgreSQL | Production-ready relational storage. |
| Vector/search - MVP | Postgres full-text or Chroma | Resume/JD chunk retrieval and similarity search. |
| Vector/search - V1 | PostgreSQL + pgvector | Store relational data and embeddings together; simpler production operations. |
| Background jobs | Celery + Redis or RQ + Redis | Run slow analysis asynchronously and retry failed jobs. |
| Scraping/fetching | Requests + BeautifulSoup + Playwright fallback | Static pages first; browser rendering only when needed. |
| UI | FastAPI Swagger for MVP; Next.js later | Start fast, add polished dashboard later. |
| Observability | Structured logs + Prometheus metrics; CrewAI tracing if available | Measure latency, cost, failures, and agent behavior. |
| Packaging | Docker Compose | Local stack: API, DB, Redis, worker. |
| LLM provider layer | CrewAI LLM config / LiteLLM optional | Keep model provider configurable. |
| Report exports | Markdown, JSON, generated DOCX, generated LaTeX, local `tectonic`/`pdflatex` PDF | Keep report source evidence-backed, provide an editable resume export, and compile PDFs behind server-side guards. |
| Testing | Pytest + Playwright | Backend unit/integration tests plus dashboard browser smoke. |

## MVP dependency groups

### Core backend

```text
fastapi
uvicorn
pydantic
sqlalchemy
alembic
python-dotenv
```

### Resume parsing

```text
pypdf
python-docx
beautifulsoup4
markdown
```

### Job fetching

```text
requests
beautifulsoup4
playwright
readability-lxml
```

### Agent workflow

```text
crewai
litellm optional
openai or chosen provider SDK
```

### Data/search

```text
sqlite for MVP
postgresql + pgvector for V1
chromadb optional for local vector MVP
```

### Reliability

```text
redis
celery or rq
tenacity
prometheus-client
structlog
```

### Testing

```text
pytest
httpx
respx
freezegun
```

## Why not make everything agentic?

A job application product needs correctness more than "creative autonomy". The MVP should use agents for reasoning and writing, but not for the core truth decisions.

Use deterministic code for:

- file parsing
- skill normalization
- match scoring
- unsupported-claim validation
- report schema validation
- authorization checks
- caching and retries

Use agents for:

- understanding ambiguous job language
- mapping responsibilities to resume evidence
- writing better bullets
- drafting a cover letter
- generating interview questions
- explaining recommendations

## Storage choice

Start with SQLite because it keeps the demo simple. Move to PostgreSQL when adding multiple users, queues, and production deployment.

Recommended production tables:

- users
- resumes
- resume_sections
- resume_facts
- job_descriptions
- job_skills
- analyses
- report_sections
- audit_events
- model_runs
- validation_failures

## Vector/search choice

For MVP, simple keyword matching and fuzzy synonyms may be enough. Add embeddings when you need semantic matching such as "backend API design" matching "RESTful service development".

Recommended V1 approach:

- PostgreSQL for structured records.
- pgvector for embeddings.
- Full-text search for exact keywords.
- Hybrid retrieval: exact keywords + vector similarity + section filters.

## Model strategy

Use a provider-agnostic LLM wrapper.

- Parsing tasks: lower-cost, fast model with structured outputs.
- Cover letter and interview tasks: stronger model only if quality fails evals.
- Validation tasks: deterministic code first, LLM second only for explanations.
- Keep temperature low for extraction and scoring.
- Use schema-constrained outputs wherever possible.

## Development environment

```text
Python 3.11+
Docker Desktop or Docker Engine
OpenClaw installed locally
GitHub repo
.env file for secrets
```

## Production-like local stack

```text
api: FastAPI
worker: Celery/RQ worker
db: PostgreSQL
redis: queue/cache
openclaw: local gateway outside compose or connected through host network
```
