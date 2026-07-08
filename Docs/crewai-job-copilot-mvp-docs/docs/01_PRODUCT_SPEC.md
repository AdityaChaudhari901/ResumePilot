# 01 - Product Specification

## Product name

CrewAI Job Application Copilot

## One-line pitch

A chat-triggered, evidence-backed job application copilot that compares a user's resume with a job description and generates truthful, tailored application material.

## Target users

### Primary user

Students, freshers, junior developers, and job seekers who apply to multiple roles and need faster resume tailoring, cover letter drafts, and interview preparation.

### Secondary user

Career coaches, placement cells, bootcamps, and resume-review services that want a semi-automated first-pass analysis tool.

## Core problem

Most job seekers manually read job descriptions, identify required skills, edit resume bullets, draft cover letters, and prepare interview questions. This is repetitive and error-prone. A normal chatbot can help, but it may hallucinate claims or provide generic advice. This MVP solves that by combining deterministic extraction, skill matching, structured outputs, and validation.

## MVP user stories

### Resume setup

As a user, I can upload my resume once so the system can reuse it across many job applications.

Acceptance criteria:

- Supports PDF, DOCX, TXT, and Markdown.
- Extracts contact info, education, skills, projects, work experience, certifications, and links.
- Stores a structured `ResumeProfile`.
- Flags low-confidence extraction fields for review.

### Job analysis

As a user, I can send `/job <url>` or paste a job description so the system can analyze the role.

Acceptance criteria:

- Extracts company, role title, location, employment type, responsibilities, required skills, preferred skills, experience level, keywords, and benefits if present.
- Uses direct text input when scraping fails or the page blocks access.
- Does not bypass authentication or paywalls.

### Match report

As a user, I receive a job-fit report that tells me where I match and where I am missing.

Acceptance criteria:

- Shows match score by category.
- Shows matched skills with resume evidence.
- Shows missing or weak skills.
- Shows role-specific strengths.
- Shows risk areas and suggested learning priorities.

### Resume tailoring

As a user, I receive suggested bullet improvements that are truthful and ATS-friendly.

Acceptance criteria:

- Every generated bullet must reference a resume evidence ID.
- Unsupported additions are marked "add only if true".
- Suggestions improve action verbs, measurable outcomes, and JD keyword alignment.
- The app does not fabricate years of experience or achievements.

### Cover letter

As a user, I receive a concise cover letter draft.

Acceptance criteria:

- Uses the company and role name when available.
- Uses only validated resume facts.
- Avoids generic overclaiming.
- Includes a confidence notice if company/job details are incomplete.

### Interview preparation

As a user, I receive interview questions based on the JD and my gaps.

Acceptance criteria:

- Questions are grouped into technical, behavioral, project-specific, and gap-focused categories.
- Includes suggested answer points from resume evidence.
- Includes "prepare more" notes for missing skills.

## In-scope for MVP

- Local FastAPI API.
- SQLite for development storage.
- Resume parser.
- Job description fetcher and parser.
- Deterministic skill matcher.
- CrewAI agents for structured analysis and writing.
- Markdown and JSON reports.
- OpenClaw `/job` command integration.
- Basic web UI or Swagger UI for resume upload.
- CLI for local demo.
- Audit logs.

## Out of scope for MVP

- One-click job submission.
- Auto-filling external application forms.
- LinkedIn/Indeed account automation.
- Email sending without approval.
- Multi-tenant enterprise accounts.
- Payment integration.
- Browser extension.
- Guaranteed ATS ranking.
- Claims of 100 percent hiring success.

## Key product constraints

- Resume data is sensitive personal data.
- Job descriptions are untrusted external content.
- LLM outputs can be wrong.
- OpenClaw should be treated as a trusted single-user local gateway, not as a hostile multi-tenant security boundary.
- Web scraping must obey site rules and provide paste fallback.

## Definition of done for MVP

- End-to-end flow works with a sample resume and at least 10 sample job descriptions.
- Reports are generated in less than 30 seconds for normal pasted job descriptions.
- Deterministic match engine returns stable results for the same inputs.
- The validator blocks unsupported claims.
- Tests cover parsing, matching, report validation, and API endpoints.
- README includes setup, demo, architecture, and security notes.
