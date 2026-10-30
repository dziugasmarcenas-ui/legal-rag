# Lessons from SENTRY, applied to legal-rag

**Date:** 2026-10-30  
**Status:** Advice, not a plan. The plan is `docs/superpowers/plans/2026-10-30-openai-mcp-mvp.md`.  
**Audience:** whoever builds the next version of this repo, including future-me.

SENTRY is a Defence Standards Intelligence RAG with the same structural problem
this repo has: a model answering questions over a large corpus of authoritative
text, where a confident wrong answer is worse than no answer. It has been in
production long enough to have made most of the expensive mistakes already. This
document is what transfers — the parts that cost real time to learn.

Nothing here is confidential. SENTRY's specific thresholds, gold sets, evaluation
taxonomy and prompt engineering are **not** included, deliberately, and this
document should stay that way if it is ever published.

---

## The strategic bet

Teisora will demo better than this repo on day one. "Ask a legal question, get a
paragraph" always demos better than "here is the article, the edition, the
paragraph, and the reason I am unsure." Racing on prose quality is a race against
a well-funded model provider, and the model is not the moat.

The moat is being **the component an agent can cite without getting burned**.

Three consequences follow, and they organise everything below:

1. The product is the citation, not the answer. The answer is the LLM host's job.
2. A refusal is a feature and needs as much design as an answer.
3. Being open source is an asset here. Trust tooling only works if it is
   auditable. Publish the machinery, keep the tuned artifacts.

---

## 1. Relevance ≠ applicability ≠ answer

Three distinct stages, three distinct failure rates, and the middle one is where
products die.

In SENTRY's evaluations, the largest single source of error was not bad
retrieval. It was **the right clause being retrieved and then not used in the
answer** — the retrieval got credit, the user got a weak or wrong response. A
Recall@5 of 0.920 says nothing about whether the generator used the article it
was handed.

**For this repo:** your golden set scores retrieval only. Every published number
describes the candidate list, not the product. Add one stage-level measurement —
"gold article present in context → article cited in answer" — before touching
embeddings or prompt wording.

**Check:** a metric in `eval/` that reports retrieval hit, use-in-answer, and
citation correctness as three separate rates. If you cannot separate them, you
cannot tell which layer you changed.

## 2. Serving must equal measurement

You already have this bug. The eval reranks the top 5 candidates; `main.py`
retrieves `TOP_K = 3` and reranks only those three. The reranker never sees the
article ranked 4th or 5th. The deployed Recall@1 is not the published 0.880.

This is the most common and most corrosive class of bug in RAG products: the
measured path and the served path drift, and every number in the README silently
becomes fiction. It usually happens for boring reasons — a constant duplicated
between two files, a function copied rather than imported.

**For this repo:** one retrieval function, imported by both the API and the eval.
No constants that exist twice.

**Check:** a test that builds the exact request `main.py` builds, runs it through
the eval harness, and asserts the returned source list is identical to what the
eval path produces. One assertion, permanent protection.

## 3. Abstention is a product surface, not a fallback

SENTRY shipped a release where every refusal rendered the same two sentences
regardless of cause. Users read that as a broken product, not a cautious one.
The refusal had the right *behaviour* and the wrong *information*.

A refusal must say what was missing, because the four cases need four different
next actions:

| Cause | What the user should be told |
|---|---|
| No article matches the topic | The Code does not appear to address this; here is what was searched. |
| Article matched but does not address the specific situation | Closest article, and the specific element that is absent. |
| Corpus edition expired | Answers describe law as of `valid_until`; verify against the current edition. |
| Ambiguous question (which employment relationship?) | One clarifying question, no answer. |

**For this repo:** the 0.54 gate returns a boolean. Add a `refusal_reason` enum
alongside it, and render it in the UI and in the MCP response.

**Check:** one test per refusal reason. A 403-word answer to a question the Code
does not cover is a failure even if the refusal was "correct".

## 4. Freshness is a safety property

Your corpus edition expires 2026-10-31. After that date every answer describes
superseded law, and the disclaimer in the UI becomes false.

SENTRY treats rights and validity as fail-closed filters that run **before**
evidence is exposed, not as metadata displayed after the fact. The same ordering
applies here: an expired edition must stop being citable, not just get a badge.

**For this repo:**

- `edition_date` and `valid_until` on every document, not on the corpus as a whole.
- `/health` and the `corpus_info` MCP tool report current edition and staleness.
- A CI check that fails when the corpus ages past N days. A green build that
  serves expired law is worse than a red build.
- Refuse, or loudly qualify, when `today > valid_until`.

**Check:** a test that freezes the clock past `valid_until` and asserts the
response carries `corpus_stale` and that the gate cannot return high confidence.

## 5. Evidence and inference must be visually separable

In SENTRY the provenance chain is literal — page text to source span to geometry
fragment to rectangle on the original PDF — because the original document is the
trust anchor and anything derived from it is flagged as derived.

Scale that down rather than copying it. The transferable rule is: **every
sentence in an output is either a quotation from a specific article, or an
interpretation, and the two are never styled the same.**

This is also the best prompt discipline available. Force structure instead of
hoping for it:

- citations are retrieved and attached by the retriever, never generated by the model
- the model emits claims that reference a citation ID, or it emits nothing
- unquoted legal text in the answer is a defect, not a paraphrase

**Check:** a test that asserts every citation in a response resolves to an
article ID that was in the retrieved set. Any citation not traceable to a
retrieval result is fabrication by definition.

## 6. Freeze the benchmark, then starve it

The frozen golden set (25 answerable questions plus 5 unanswerable controls)
stops being a measurement and becomes a target within about a month of you
tuning against it. `threshold_sweep.py` and `rerank_experiment.py` both tune
against it, so the 0.54 gate is already fit to those 30 cases.

**For this repo — keep the frozen set for regression, and add two more:**

- a **private held-out set**, never used for prompt or threshold tuning, drawn
  from real questions and incidents
- an **adversarial set** for the failure modes that matter here: questions about
  law that changed recently, questions where the closest article is a decoy,
  questions that are not employment law at all

Never delete a failing case. Add it, and let the suite grow monotonically.

**Check:** the frozen set's score is reported alongside the held-out score. A
gap between them is the overfitting signal.

## 7. Choose the provider by blind measurement, or do not claim it

"OpenAI understands Lithuanian best" is currently unfalsifiable in this repo.
There is no generation benchmark, so the Haiku→Sonnet change rests on one
hand-caught translation error, and the OpenAI switch rests on a hypothesis.

A single hand-caught sentence is a good reason to *test*, not a good reason to
*claim*. Both are legitimate — but only one of them can be defended in a README.

**For this repo:** blind comparison over the same retrieved context — providers
× N questions, shuffled and labelled, graded on factual fidelity, citation
fidelity, Lithuanian grammaticality and correct refusal. Publish the table either
way. A published negative result is more persuasive than an unpublished claim,
and it is the cheapest credibility available.

**Check:** `eval/generation/` with a harness that takes a provider list as a
parameter, and a results table committed next to the numbers in the README.

---

## The MCP tool surface is the product

An MCP consumer will stitch several calls together. That makes the tool contract
more important than the prompt, and Teisora-shaped `search` / `get` / `ask` is
table stakes rather than differentiation. The differences that matter are
structural and cheap:

| Requirement | Why |
|---|---|
| `as_of_date` on every retrieval | Law is time-indexed. An agent answering a 2019 question needs the 2019 text. |
| Paragraph-granular, stable article IDs (`LC-127-2`) | Section-level IDs make citations unusable and diffing impossible. |
| Structured citation objects | Never return prose that happens to contain an article number. Return `{article, paragraph, edition, quote, url}`. |
| Deterministic ordering and explicit `rank`/`score` | An agent cannot reason about a list it cannot reproduce. |
| Pagination | Top-3 truncation is the bug in §2 wearing a different hat. |
| Error taxonomy | `not_found` ≠ `no_law_addresses_this` ≠ `corpus_stale` ≠ `provider_unavailable`. Four different caller behaviours. |
| No query-text logging | Legal questions are sensitive by default. Log tool, latency, gate outcome, cost — never `q`. |
| Honest `corpus_info` | Edition, coverage, known gaps. Worth more to a consumer than a tenth of a point of Recall@1. |

**Check:** the contract test suite is written against the MCP schema, not against
your implementation. If it only passes because of an internal detail, it is not a
contract.

---

## The open-source boundary

Publish the method, not the tuned artifacts. Concretely:

**Open (this is the credibility):**

- the retrieval and citation plumbing
- the abstention logic and its reason taxonomy
- the eval *harness* and the frozen regression set
- the parity test that keeps serving honest
- the corpus freshness machinery
- the generation benchmark methodology and results

**Hold (these are the product):**

- the tuned confidence threshold and the data it was calibrated on
- the private held-out and adversarial question sets
- any failure-mode taxonomy you invested real time in
- provider-specific prompt engineering
- any corpus material whose rights status is unresolved

**Rights rule, stated once:** "publicly available" is not permission.
"Consolidated edition is free to read on a government site" is not permission to
redistribute it inside an open-source package. Keep a per-document rights state,
fail closed, and do not let an agent or a script silently promote an unresolved
document to "cleared". If the determination is not already explicit, it is
unresolved, and it stays that way until a human decides.

---

## What *not* to copy from SENTRY

Being honest about this is part of the value. SENTRY is a multi-agent,
multi-month build with a large surface area, and much of that was paid for in
scope that a solo MVP cannot afford:

- **Do not copy the scope.** SENTRY has feature flags, staged rollouts, several
  redundant gates and an acquisition pipeline. You need one tool, one corpus,
  one gate, one deploy.
- **Do not build a second chatbot.** The host model is better than anything you
  will tune, and it already has the conversation. Ship retrieval.
- **Do not add a framework.** No LangChain, no agent orchestration layer. The
  core is a few hundred lines and should stay that way.
- **Do not tune thresholds before you have a use-in-answer metric.** You will
  optimise a number that does not correspond to the product.
- **Do not treat a passing test suite as proof.** SENTRY's most expensive defects
  were found by looking at rendered output, not by running tests.

---

## Sequence

Ordered by cost of being wrong, not by effort:

1. **Corpus edition refresh** — breaks tomorrow; everything else is cosmetic until this is fixed.
2. **Serving = measurement** — restore the truth of the numbers you already publish.
3. **Freshness machinery** — `valid_until`, staleness refusal, CI check.
4. **Refusal reasons** — four strings, four behaviours.
5. **Use-in-answer metric** — the missing middle stage.
6. **Generation benchmark** — settle the provider question with a table.
7. **MCP core, then remote, then auth** — as already planned.
8. **Held-out and adversarial sets** — before the first public number is claimed.
