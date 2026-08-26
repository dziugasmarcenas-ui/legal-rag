# Employer Portfolio Presentation Implementation Plan

> **Execution:** Implement inline with one verified commit per task.

**Goal:** Make the shipped V1 immediately understandable and credible to applied-AI employers.

**Spec:** `docs/superpowers/specs/2026-08-26-employer-portfolio-presentation-design.md`

## Constraints

- Use only existing measured evidence.
- Preserve the detailed README methodology and limitations.
- Keep product behavior and legal data unchanged.
- Do not create or discuss a V2 roadmap.
- Use genuine application output for the screenshot.

### Task 1: Documentation contract

- Create `tests/test_portfolio_docs.py` checking shipped status, headline metrics, unique methodology heading, artifact existence, README navigation, and absence of a V2 plan link.
- Run it and confirm it fails for the missing presentation artifacts.
- Commit the test.

### Task 2: Employer-first README

- Replace the opening with live link, screenshot, headline results, ownership, stack, and portfolio navigation.
- Convert stale scope into a completed V1 delivery record with post-scope additions documented honestly.
- Remove duplicated content without deleting technical evidence.
- Run the README contract test and commit.

### Task 3: Case study, demo, and application copy

- Create `docs/portfolio/CASE_STUDY.md` as a 3–5-minute problem-to-outcome narrative.
- Create `docs/portfolio/DEMO.md` with a 90-second script and four-minute interview walkthrough.
- Create `docs/portfolio/APPLICATION_BULLETS.md` with CV, LinkedIn, GitHub, and role-specific copy.
- Verify all metrics against README and commit.

### Task 4: Genuine screenshot

- Load the in-app browser skill and open the live application.
- Submit the annual-leave example and verify a successful cited answer containing article 126 above the 0.54 gate.
- Capture the answer, confidence display, and source card to `docs/assets/legal-rag-answer.jpg`.
- Inspect the image for readability and privacy, then commit.

### Task 5: Final audit

- Run the complete pytest suite, JavaScript syntax check, and `git diff --check`.
- Check every relative Markdown link and every numeric claim.
- Confirm no V2 artifact was created and no video is claimed as published.
- Review the branch diff and report the remaining user action: record the demo using the supplied script.
