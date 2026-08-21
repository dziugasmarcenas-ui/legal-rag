# legal-rag

[![ci](https://github.com/dziugasmarcenas-ui/legal-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/dziugasmarcenas-ui/legal-rag/actions/workflows/ci.yml)

A retrieval-augmented question answering system over the **Lithuanian Labour Code**
(*Lietuvos Respublikos darbo kodeksas*, act no. XII-2603).

Ask an employment-law question in plain language; get an answer grounded in a
specific article of the code, with the article cited — or an honest refusal when
the code does not contain the answer.

> **Status: build sprint in progress (started 2026-08-20).**
> Every number in this README is either measured and dated, or explicitly marked
> as not yet measured. Nothing is claimed that has not been run and observed.

---

## Scope — frozen 2026-08-20, hour 0.75

This section is a contract with myself. Anything not listed here does not ship.

### In scope

- [ ] Corpus: consolidated Darbo kodeksas (XII-2603), parsed to article-level records
      carrying `article`, `title`, `text`, `source`, `act_number`, `edition_from`, `edition_to`
- [ ] Article-level chunking, embeddings persisted to disk (re-runs do not re-embed)
- [ ] Top-k dense retrieval, inspectable with zero LLM calls
- [ ] Confidence gate that abstains rather than guessing
- [ ] `POST /chat` and `GET /health` over HTTP, publicly deployed
- [ ] A golden set of 30 questions (~5 unanswerable), each expected article
      manually verified, **frozen before any tuning**
- [ ] Two separate benchmarks: retrieval quality and abstention behaviour
- [ ] One measured baseline, one diagnosed failure, one justified fix, one rerun

### Explicitly out of scope

- Any frontend beyond a `curl` example
- Multilingual answering beyond what the corpus language forces
- Legal advice. This is an information-retrieval demo, not counsel.
- Reranking, hybrid/BM25 search, query rewriting, agentic retrieval —
  not because they are bad ideas, but because an unmeasured system cannot
  justify them and this sprint is capped at 20 hours.

### Success criteria

The build is done when a stranger can open a URL, ask a Lithuanian employment-law
question, receive a cited answer or an honest refusal, and read this README to
learn exactly how well it works and where it fails.

---

## Corpus

| Field | Value |
|---|---|
| Source | *Lietuvos Respublikos darbo kodeksas* |
| Approving act | XII-2603 (the Code is annexed to it, not identical to it) |
| Published | TAR 2016-09-19, i. k. 2016-23709 |
| Consolidated edition valid from | **2026-06-07** |
| Consolidated edition valid to | **2026-10-31** |
| Retrieved from | e-TAR, act id `f6d686707e7011e6b969d7ae07280e89`, retrieved 2026-08-20 |
| Articles parsed | **257** |
| Coverage | Complete Code, all four parts. Articles 1-260, less repealed 85-88, plus 72¹ |

The system answers against **that specific consolidated edition**, not against
"Lithuanian law" generically. When the law changes, the benchmark below becomes
a measurement of a historical edition — which is why the edition is pinned here.

---

## Architecture

`NOT YET BUILT — diagram goes here (hour 17.5)`

---

## Chunking rationale

`NOT YET WRITTEN — see hour 17.5`

---

## Results

### Retrieval benchmark

Answerable questions only. Measures whether the correct article appears in the
top-k retrieved results — independent of whether the language model then writes
a good answer. Retrieval failure and generation failure are different bugs and
are measured separately here on purpose.

| Metric | Baseline | After fix |
|---|---|---|
| Recall@1 | 0.720 (18/25) | **0.880** (22/25) |
| Recall@3 | 0.840 (21/25) | **0.920** (23/25) |
| Recall@5 | 0.920 (23/25) | 0.920 (23/25) |

### The one change, and why it was that one

Failure analysis over the seven Recall@1 failures found a dominant pattern:
**mechanism-first retrieval**. The embedding reliably reaches the right legal
neighbourhood but underweights the qualifier that decides which article inside it
governs -- who is acting, why, which subtype. Article 64 (*notice, generally*)
outranked article 57 (*redundancy*); article 147 (*late wage payment*) outranked
both article 130 (*holiday pay*) and the dispute-resolution articles.

Recall@1 0.720 against Recall@5 0.920 pointed the same way: candidate generation
is strong, ordering is weak.

So exactly one thing changed -- **the same five candidates were reordered by a
cross-encoder reranker** (`voyage rerank-2.5`). The corpus, chunking, embeddings,
golden set and its labels were untouched, and the candidates were taken from the
cached baseline retrieval rather than re-retrieved.

`Recall@5` acts as the experiment's control: reordering five items cannot change
whether the correct article is among them. It held at 0.920, so nothing else
leaked in.

Four questions improved (ranks 4→1, 4→1, 2→1, 3→1), none regressed. Two questions
did **not** improve -- their correct articles were never in the candidate set, and
a reranker cannot retrieve what retrieval missed. That limit is the useful part of
the result: it separates a ranking failure from a candidate-generation failure
with evidence rather than assertion.

### Abstention benchmark

Run over both answerable and unanswerable questions.

| Metric | Baseline | After fix |
|---|---|---|
| Unanswerable correctly refused | **0.800** (4/5) | `NOT YET MEASURED` |
| Answerable falsely refused | **0.720** (18/25) | `NOT YET MEASURED` |

> The abstention benchmark is **exploratory**: the golden set contains only
> ~5 unanswerable questions. Sample size is stated so the number is not
> mistaken for a reliable rate.

### Confidence threshold

The operating point is chosen from this sweep, not assumed.

| Threshold | Unanswerable correctly refused | Answerable falsely refused |
|---|---|---|
| 0.40 | 0.600 (3/5) | 0.080 (2/25) |
| 0.50 | 0.800 (4/5) | 0.720 (18/25) &larr; deployed |
| 0.60 | 0.800 (4/5) | 1.000 (25/25) |

Chosen operating point: `NOT YET CHOSEN` — pending the hour-13.5 failure analysis.

**The score ranges overlap completely.** Answerable questions score 0.3573&ndash;0.5627
at rank 1; unanswerable ones score 0.3246&ndash;0.6050. One unanswerable question
outscores every answerable one, so **no single absolute-similarity threshold provides
useful separation**: catching the fifth unsupported query would require a threshold
that also rejects every answerable query in the benchmark. This is a limitation of
using an absolute similarity score as a confidence signal, not a tuning problem.

---

## Methodology and integrity notes

- The golden set was frozen **before** any tuning. Any change made to it after
  the freeze is recorded here, with the reason.
- Post-freeze golden set changes: *none yet.*
- Corpus caveat: e-TAR text extraction flattens superscript article numbers, so
  article 72¹ arrives as `721`. It is caught because 721 falls outside the valid
  range 1-260 and is remapped. A superscript article whose flattened form
  collided with a real article number (12¹ rendering as `121`) would be
  undetectable from this text alone. No such collision exists in this edition -
  article IDs were checked for duplicates and none were found.
- Every expected-article label in the golden set was verified by hand against the
  source document, not generated by a model.
- Continuous integration runs on every push: metric unit tests, Gate A (corpus
  integrity) and Gate C (golden set frozen and unchanged). Both gate scripts exit
  non-zero on failure, so a broken corpus or an edited benchmark fails the build
  rather than being noticed later.
- Corpus verification (Gate A): all automated checks in `check_corpus.py` pass --
  unique IDs, no empty text, no amendment annotations or structural headers
  leaking into article bodies, numbering reconciled, edition dates on every
  record. Of the ten-article manual sample, article 174 was verified in full
  against e-TAR line by line; the remaining nine were checked at title and
  opening-line level.

---

## Honest history

Version 1 of this project ran retrieval over **five hand-written English
paraphrases** of Lithuanian labour law, used top-1 retrieval, had one hardcoded
question, and used a `0.5` confidence threshold picked arbitrarily.

Recall@3 over five documents is trivially near-perfect, which made retrieval look
far better than it was. Preparing the project for real evaluation made clear that
it was not a meaningful benchmark. It was replaced with the actual consolidated
Labour Code, and a manually verified golden set was frozen before anything was
tuned.

The v1 prototype is preserved in this repository's first commit.

---

## Limitations

`NOT YET WRITTEN — see hour 17.5`

---

## Running it

`NOT YET WRITTEN`

---

## Licence and disclaimer

The Labour Code is public legal text of the Republic of Lithuania. This project
is a technical demonstration of retrieval-augmented generation and **is not legal
advice**. Verify anything that matters with a qualified professional or the
official consolidated text on e-TAR.
