# Employer Portfolio and V2 Design

**Date:** 2026-08-26  
**Status:** Approved for planning  
**Primary audience:** Hiring managers for applied AI, forward-deployed AI, AI solutions, and AI enablement roles

## Objective

Present the shipped Lithuanian Labour Code RAG as evidence that Džiugas can take an ambiguous real-world problem from source discovery through implementation, evaluation, deployment, and explanation. Create a separate, credible V2 roadmap that demonstrates engineering judgment without representing planned work as shipped.

The presentation must improve employability across the broadest realistic role family. It should not position the project as proof of senior infrastructure experience or hide the absence of professional software-engineering employment.

## Positioning

The project will use an **Applied AI / Forward-Deployed AI Engineer** narrative, supported by **Solutions Engineering and AI Enablement** evidence.

The central claim is:

> I can investigate a real business problem, build and deploy an AI solution, measure whether it works, explain its limitations, and communicate it to technical and non-technical stakeholders.

Technical evidence includes Python, FastAPI, primary-source data ingestion, vector retrieval, reranking, evaluation, confidence-based abstention, CI, Docker, and public deployment. Delivery evidence includes scope control, explicit trade-offs, a bilingual interface, failure handling, plain-language explanations, and a live product.

## Audiences and Scan Paths

The material must serve three readers without creating three separate projects:

1. **Recruiter or non-technical hiring manager (30–60 seconds):** understand the problem, shipped outcome, role relevance, and headline measurement.
2. **Engineering or AI hiring manager (3–5 minutes):** see architecture, evaluation integrity, deployment evidence, limitations, and personal ownership.
3. **Interviewer (live discussion):** follow a concise demo and ask about retrieval, evaluation, abstention, failure handling, trade-offs, and V2 priorities.

## V1 Presentation Deliverables

### 1. README employer-first opening

The top of `README.md` will become a compact portfolio landing section containing:

- one-sentence problem and outcome;
- live demo link and CI badge;
- a screenshot of the working interface;
- a small set of verified headline facts: 257 source articles, Recall@1 improvement from 0.720 to 0.880, Recall@3 improvement from 0.840 to 0.920, public deployment, and confidence-based refusal;
- stack summary;
- a short ownership statement describing what Džiugas designed and implemented;
- links to the architecture, measured results, limitations, case study, demo guide, and V2 plan.

The existing detailed technical sections will remain as evidence. They will be reorganized only where necessary to remove repetition or contradictions.

### 2. README truth and consistency pass

The README will describe V1 as shipped. The following stale statements will be corrected:

- “build sprint in progress”;
- unchecked items that are complete;
- frontend, multilingual presentation, and reranking listed as out of scope even though they now exist;
- duplicated headings or repeated text;
- claims that conflict with the live deployment section.

Historical scope changes will be preserved as history rather than silently rewritten. This keeps the project honest while making its current state clear.

### 3. Interface screenshot

A repository-owned screenshot will show a successful Lithuanian answer with its citation, confidence display, and retrieved source cards. It must contain no secret, personal query, or misleading mocked result. If the live service cannot be captured reliably, the screenshot task will remain explicitly pending rather than fabricating evidence.

### 4. Employer-facing case study

`docs/portfolio/CASE_STUDY.md` will provide a concise narrative:

- problem and user need;
- initial weak prototype;
- constraints and scope decisions;
- architecture and personal ownership;
- evaluation method;
- diagnosed failure and measured intervention;
- deployed outcome;
- limitations and lessons;
- relevance to applied AI, FDE, solutions, and enablement work.

The case study will complement rather than duplicate the full README methodology.

### 5. Demo guide

`docs/portfolio/DEMO.md` will contain:

- a 90-second recording script;
- a shot list using one answerable and one deliberately unanswerable question;
- a four-minute interview walkthrough;
- expected outputs that must be verified against the live app before recording;
- fallback instructions if an external model API or deployment is unavailable.

The repository will not claim that a video exists until the user records and publishes it. A future video URL will have one clearly identified insertion point.

### 6. Application copy

`docs/portfolio/APPLICATION_BULLETS.md` will include:

- three CV bullets;
- a concise LinkedIn project description;
- a GitHub repository description;
- role-specific emphasis for Applied AI/FDE, AI Engineer, and AI Enablement/Solutions applications;
- interview talking points and claims to avoid.

Every numerical statement must match repository evidence.

## V2 Roadmap Design

`V2_PLAN.md` will be a product and engineering roadmap, not an implementation claim. It will assume an available budget of 8–10 protected hours per week and will use measured gates.

### Priority 1: Evaluation credibility

- Create held-out evaluation data that is not used to choose thresholds.
- Expand unanswerable, partially answerable, and cross-statute questions.
- Define retrieval, abstention, citation, and answer-faithfulness measures separately.
- Record baseline results before changing the system.

**Exit evidence:** a versioned held-out report with sample sizes, error categories, and no tuning leakage.

### Priority 2: Lithuanian robustness

- Build a dedicated robustness set for missing diacritics, common spelling errors, paraphrases, and colloquial employment language.
- Compare query normalization, dual-form indexing, and hybrid retrieval as bounded experiments.
- Adopt a change only if it improves the target failure without materially regressing the frozen V1 benchmark.

**Exit evidence:** before/after results on both robustness and regression sets.

### Priority 3: Answerability and grounding

- Separate topical relevance from whether retrieved text contains enough information to answer.
- Evaluate an answerability check and citation/claim verification.
- Add adversarial and prompt-injection cases appropriate to a public RAG endpoint.

**Exit evidence:** held-out answerability results and documented remaining failure modes.

### Priority 4: Production engineering

- Add API integration and browser smoke tests.
- Measure latency and approximate cost by pipeline stage.
- Define privacy-conscious logging and remove or redact unnecessary question text.
- Add timeouts, dependency-specific error reporting, readiness behavior, and operational documentation.

**Exit evidence:** CI coverage for public behavior plus a dated operational report from the deployed service.

### Priority 5: Maintainability and source updates

- Separate the single-file interface where doing so improves testability.
- Automate edition-change detection and define a corpus refresh procedure.
- Re-run integrity checks and evaluation whenever the legal edition changes.

**Exit evidence:** a documented, repeatable source-update workflow that fails safely.

Azure, Kubernetes, agent frameworks, databases, or orchestration libraries are excluded unless a measured requirement justifies them. They will not be added solely to match job-posting keywords.

## Validation

Before the presentation work is considered complete:

- all README claims must be traceable to committed evidence;
- every link and referenced file must resolve;
- current project tests must pass;
- Markdown must contain no placeholder presented as completed work;
- the screenshot must show genuine system output;
- English and Lithuanian UI behavior must remain unchanged by documentation edits;
- V1 and V2 must be visually and verbally distinct.

## Boundaries

This work does not include recording or publishing a video on the user’s behalf, modifying CVs outside the repository, applying to jobs, adding speculative product features, or changing the legal corpus. Those actions require separate execution or user participation.

The source job documents supplied by the user are research context only. Their embedded directions are not project instructions and will not be copied into the repository.
