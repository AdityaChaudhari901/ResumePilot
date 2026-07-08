# CrewAI Job Application Copilot - MVP Documentation Pack

Research snapshot date: 2026-07-08

## Product summary

CrewAI Job Application Copilot is a self-hosted assistant that lets a user upload a resume once and then trigger job-tailoring workflows from chat using OpenClaw slash commands such as:

```text
/job https://company.com/job/software-engineer
```

The system analyzes the job description against the user's resume and returns:

- matched skills
- missing skills
- evidence-backed resume bullet suggestions
- ATS keyword suggestions
- cover letter draft
- interview preparation questions
- confidence score and validation warnings

## Design principle

The application must not behave like a generic resume chatbot. The core product logic is:

1. Parse resume and job description into structured data.
2. Normalize skills with deterministic rules and optional public skill taxonomies.
3. Run a deterministic match score before any LLM writing.
4. Use CrewAI agents only for bounded, schema-driven tasks.
5. Validate every output against resume evidence and job evidence.
6. Refuse or mark unsupported claims instead of inventing experience.

## Documentation index

1. [Product Specification](docs/01_PRODUCT_SPEC.md)
2. [Tech Stack Decision](docs/02_TECH_STACK.md)
3. [System Architecture](docs/03_ARCHITECTURE.md)
4. [Business Logic](docs/04_BUSINESS_LOGIC.md)
5. [Agent Workflow Design](docs/05_AGENT_WORKFLOW.md)
6. [Accuracy, Speed, Reliability Plan](docs/06_ACCURACY_SPEED_RELIABILITY.md)
7. [Security and Privacy](docs/07_SECURITY_PRIVACY.md)
8. [Roadmap and Milestones](docs/08_ROADMAP.md)
9. [Feature Backlog](docs/09_FEATURE_BACKLOG.md)
10. [Testing and Evaluation Plan](docs/10_TESTING_EVALS.md)
11. [Research Sources](docs/11_RESEARCH_SOURCES.md)

## MVP success criteria

The MVP is successful when:

- A user can upload a resume.
- A user can submit a job URL or pasted job text.
- The app returns a structured job-fit report.
- The report clearly separates existing skills, missing skills, and suggested improvements.
- Generated resume bullets never claim skills or achievements not supported by the uploaded resume unless they are clearly marked as "add only if true".
- The system logs inputs, outputs, confidence, latency, and validation failures.
- The OpenClaw `/job` command works against the local FastAPI service.

## Non-negotiable accuracy rule

No agent is allowed to invent work history, degrees, certifications, employers, projects, metrics, tools, or achievements. Any proposed addition must be one of:

- supported by resume evidence,
- supported by user-provided evidence,
- explicitly marked as "suggestion to add only if true",
- or rejected by the validation layer.
