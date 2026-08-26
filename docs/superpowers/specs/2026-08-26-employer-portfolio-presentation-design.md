# Employer Portfolio Presentation Design

**Date:** 2026-08-26  
**Status:** Approved  
**Audience:** Hiring managers for applied AI, forward-deployed AI, AI solutions, and AI enablement roles

## Objective

Present the shipped Lithuanian Labour Code RAG as evidence that Džiugas can take an ambiguous real-world problem from source discovery through implementation, evaluation, deployment, and explanation. This work covers V1 presentation only and contains no V2 roadmap or future-feature plan.

## Positioning

The project uses an **Applied AI / Forward-Deployed AI Engineer** narrative, supported by **Solutions Engineering and AI Enablement** evidence:

> I can investigate a real business problem, build and deploy an AI solution, measure whether it works, explain its limitations, and communicate it to technical and non-technical stakeholders.

Technical evidence includes Python, FastAPI, primary-source ingestion, vector retrieval, reranking, evaluation, confidence-based abstention, CI, Docker, and public deployment. Delivery evidence includes scope control, trade-offs, a bilingual interface, failure handling, and plain-language explanations.

## Deliverables

### Employer-first README

The opening must communicate the problem, live result, measured improvement, stack, ownership, and limitations within 60 seconds. It will link to a genuine screenshot, case study, demo guide, and application copy. Existing deep technical evidence remains below the summary.

Stale statements will be corrected: “build sprint in progress,” unchecked completed work, shipped features still listed as out of scope, repeated headings, and contradictions with the live deployment section. Historical scope changes remain visible as history.

### Genuine interface screenshot

`docs/assets/legal-rag-answer.png` will show a successful Lithuanian answer, citation, confidence display, and source card from the real application. It must contain no secrets, personal queries, or fabricated output. If the live service cannot produce the expected result, the screenshot is blocked rather than mocked.

### Case study

`docs/portfolio/CASE_STUDY.md` will cover the user problem, weak first prototype, V1 architecture, personal ownership, frozen evaluation, diagnosed failure, measured intervention, deployment, limitations, lessons, and employer relevance in a 3–5-minute read.

### Demo and interview guide

`docs/portfolio/DEMO.md` will contain a 90-second recording script, shot list, four-minute interview walkthrough, expected live behavior, fallback guidance, and likely technical interview questions. It will not claim a published video exists.

### Application copy

`docs/portfolio/APPLICATION_BULLETS.md` will contain three CV bullets, LinkedIn copy, a GitHub description, role-specific framing, interview talking points, and claims to avoid. Every numerical statement must match repository evidence.

## Validation

- All claims trace to committed evidence.
- Metrics remain: 257 articles; Recall@1 0.720 to 0.880; Recall@3 0.840 to 0.920; Recall@5 0.920 unchanged.
- Links and referenced repository files resolve.
- Tests pass and embedded JavaScript remains valid.
- V1 limitations remain prominent and are not reframed as completed fixes.
- The screenshot shows genuine system output.
- No V2 roadmap or future-feature plan is created.

## Boundaries

This work does not record or publish a video, edit external CV files, apply to jobs, change product behavior, modify the legal corpus, or plan V2. The source job documents are research context only and their embedded directions are not project instructions.
