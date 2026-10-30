# OpenAI Switch and MCP MVP Plan

**Date:** 2026-10-30  
**Status:** Proposed — Phase 0 implemented, Phases 1–5 not started  
**Owner:** Džiugas  
**Supersedes:** uncommitted "Haiku → Sonnet" model change in `main.py`

## Goal

Turn the shipped V1 web demo into a **Lithuanian Labour Code MCP connector** — the
Teisora shape: the user brings their own AI host (Claude, ChatGPT, OpenCode) and
the connector supplies retrieval, citations, and an answerability signal. OpenAI
becomes the default answer model.

**MVP is done when:** a stranger can add the connector in Claude (or ChatGPT dev
mode), ask a Lithuanian employment-law question in their own chat, get an answer
that cites real Labour Code articles, get an explicit refusal when the Code does
not cover it, and never see a fabricated citation — all served from a public
HTTPS endpoint with a spending cap.

## What must not change

- **Citations stay retriever-attached.** The model never produces an article ID.
- **No number is republished unless it was re-measured at the configuration that
  actually serves traffic.** Two divergences exist today (see Task 1.2 and 1.3).
- **Refusals stay visible.** A refusal still returns the considered sources and
  their scores.

## Decisions

| # | Decision | Why |
|---|---|---|
| D1 | Swap **generation only**; keep Voyage for embeddings and reranking | The whole frozen benchmark (`voyage-3` + `rerank-2.5`) and every README number depend on it. There is no evidence that a different embedder improves Lithuanian retrieval on this corpus, and re-embedding invalidates Recall@1 0.720→0.880. Revisit only as a measured A/B, not as a migration. |
| D2 | Treat "OpenAI is the best Lithuanian model" as a **hypothesis to test** | The golden set scores retrieval, not prose. Nothing in this repo can currently support or refute the claim. Add a generation benchmark before repeating it publicly. |
| D3 | MCP provides **retrieval tools**; the host model writes the prose | This is the Teisora model and the reason these connectors work: the host already has a good model and a conversation. Also keeps us out of the business of being a second chatbot. |
| D4 | Also expose `ask_labour_code` (answer + sources + confidence) | Parity with the existing product, useful for hosts with weak models, and it reuses the gate. Retrieval tools remain the default path. |
| D5 | **One core, several adapters** | `retrieval`, `gate`, and the corpus are already independent of FastAPI. Extract a package so the HTTP API, MCP server, and CLI share one implementation instead of three drifts. |
| D6 | Remote **Streamable HTTP** at `/mcp` on the existing Railway service; `stdio` entry for local use | Remote is required for Claude/ChatGPT connectors. stdio keeps local development and desktop hosts simple. |
| D7 | Bearer token for MVP, OAuth 2.1 + PKCE only when a directory listing demands it | OAuth is several days of work and not needed to prove the product. ChatGPT custom connectors in developer mode and Claude custom connectors can be used without it. |
| D8 | No query-text logging | Legal questions are sensitive by default. Log tool name, latency, gate outcome, and cost — never `q`. |

## Phase 0 — Provider switch (implemented 2026-10-30)

New `llm.py`: one seam, `openai` default, `anthropic` fallback, one normalized
exception (`ProviderUnavailable`) so `main.py` cannot mistake a model outage for
"the Code does not answer this". Model and provider come from the environment at
call time, because `.env` is loaded after imports.

Files: `llm.py` (new), `main.py`, `requirements.txt`, `Dockerfile`,
`.env.example`, `static/index.html` (model name now read from `/health`),
`tests/test_llm_provider.py` (new).

**Acceptance**

- `pytest tests/` passes (24 currently).
- `GET /health` reports `answer_provider` and `answer_model`.
- A bad key produces `ProviderUnavailable`, and `/chat` still returns sources
  with `error: "answer_generation_unavailable"`.

**User action required:** add `OPENAI_API_KEY` to `.env` and to Railway. Until
then the deployed service will answer with `answer_generation_unavailable`
(sources still returned). Set `LLM_PROVIDER=anthropic` to run on the existing
Claude key in the meantime.

## Task 1.1 — Refresh the corpus (urgent, blocking)

**Status 2026-10-30:** pipeline built and verified; the new edition is not yet
published on e-TAR (the portal still serves 2026-06-07 → 2026-10-31). The
staleness guard shipped in the same pass, so the app now reports expiry on
`/health`, logs it at boot, and shows a banner instead of silently answering
from an old edition.

The loaded edition is valid **2026-06-07 → 2026-10-31**. It expires tomorrow.
Every answer the connector gives after that is an answer about superseded law,
and the disclaimer in the UI becomes false.

- Re-download the consolidated act (XII-2603) from e-TAR and extract to
  `data/darbo_kodeksas_raw.txt`.
- Update `EDITION_FROM` / `EDITION_TO` in `parse_corpus.py`; re-run
  `parse_corpus.py`, `check_corpus.py`, `embed_corpus.py`.
- Re-verify each golden-set `expected_articles` label against the new text;
  record any label change in the README's post-freeze section (`check_goldenset.py`
  will refuse a silent edit — that is the point).
- Re-run the eval and republish Recall@k only if the retrieval result actually
  moved.

Replace the manual download with the script:

```bash
python refresh_corpus.py           # prints the new window and every changed paragraph
python refresh_corpus.py --write
python parse_corpus.py && python check_corpus.py && python embed_corpus.py
```

The script reads the edition token from the portal, downloads the consolidated
DOCX, extracts paragraphs (runs, tabs and breaks handled), and compares
whitespace-insensitively. Verified on 2026-10-30: it reproduces the loaded
corpus exactly and reports no substantive change, so a "no diff" result is
trustworthy when the new edition does appear.

**Acceptance:** `python check_corpus.py` passes, `/health` shows the new edition,
golden set re-frozen with a recorded reason, README numbers match the run.

## Task 1.2 — Make serving match the measurement

`eval/` reranks the **top 5** candidates. `main.py` retrieves `TOP_K = 3` and
reranks only those three, so the deployed Recall@1 is **not** the published
0.880 — the reranker never sees the article that cosine ranked 4th or 5th.

- Retrieve `CANDIDATES = 10`, rerank them, return `TOP_K = 3`.
- Re-run `eval/run_eval.py --refresh` and the rerank experiment at exactly that
  configuration; publish the number that serves traffic.
- Fix the README architecture diagram, which currently says "top-5 candidates".

**Acceptance:** one documented pipeline constant, used by both eval and serving,
and a README number produced by it.

## Task 1.3 — Generation benchmark (the evidence for D2)

- `eval/generation_set.json`: the 30 frozen questions plus ~10 adversarial
  Lithuanian cases — every failure already named in `ANSWER_LANGUAGE` plus the
  single-parent construction (one child vs. one parent raising a child), a
  gender-agreement trap, and a numeric trap (days vs. months).
- `eval/run_generation.py`: for a fixed set of retrieved contexts, call each
  candidate model once, cache every output, and score blind against a rubric:
  **factual fidelity to the retrieved text, citation fidelity, Lithuanian
  grammaticality, refusal correctness**. Two raters or an LLM judge calibrated
  against hand labels (see the `validate-evaluator` skill); report agreement.
- Candidates: `gpt-6.1-terra`, `gpt-6-luna` (cost floor), `claude-sonnet-5`
  (incumbent).

**Acceptance:** a results table in the README with the winner marked, the cost
per 1,000 answers, and the exact prompts. If OpenAI does not win, say so.

## Phase 2 — MCP core

**Status 2026-10-30: shipped.** `mcp_server.py` serves four tools
(`corpus_info`, `search_labour_code`, `get_article`, `ask_labour_code`) over stdio
and, mounted by `main.py`, over Streamable HTTP at `/mcp`. Prompt construction
moved to `answer.py` so the API and MCP call the same one. Tests cover the
contract: typed `not_found`, per-article `above_gate`, refusal below the gate
without calling the model, and a provider outage that still returns sources.
**Part-level citations shipped** without re-chunking: `paragraphs.py` derives
the Code's own `dalis` numbering (repairing flattened superscripts such as
`2¹` arriving as `21.`), every article carries `parts`, and MCP returns them
with `126 str. 2 d.` / `126-2` style ids. Retrieval and the benchmark are
unchanged, so the published numbers still describe the served pipeline.
Re-chunking retrieval to paragraph level remains deliberately undone: it would
invalidate the benchmark for a retrieval gain that has not been measured.

**Time travel shipped for this act.** `build_history.py` discovers all 41
consolidated editions on e-TAR, downloads each DOCX, and folds them into 498
per-article versions (~1 MB). `history.py` answers "what was in force on date X"
and `get_article(article, as_of_date)` returns that day's text with part-level
citations. Retrieval stays indexed on one edition and refuses historical search
instead of faking it. Tests cover boundary dates, articles not yet enacted, and
the refusal paths.

Freshness is now automated: `check_freshness.py --online` runs in a scheduled
`freshness` workflow (not the PR gate), so a rolled-over edition turns a daily
job red instead of making every pull request red.


Extract the shared core, then wrap it.

```
legal_rag/
  corpus.py      # load + validate articles.json and vectors (moved from retrieval.py)
  retrieval.py   # embed, search, rerank
  gate.py
  answer.py      # prompt + llm.generate
  server/
    http.py      # current main.py, adapted
    mcp.py       # new
    cli.py       # python -m legal_rag "question"
```

**Tools** (names are the interface; keep them boring and explicit):

| Tool | Returns |
|---|---|
| `search_labour_code(query, k=5)` | Ranked articles: `article`, `citation`, `title`, `quote` (the passage that matched, not the whole article), `cosine_score`, `rerank_score`, `above_gate` |
| `get_article(article)` | Full article text, title, citation, edition dates, e-TAR link |
| `corpus_info()` | Article count, edition window, embedding/rerank models, abstention threshold, disclaimer |
| `ask_labour_code(question, lang="lt")` | `answer`, `sources`, `confidence`, `refused` — same contract as `POST /chat` |

Rules the server enforces, not the prompt:

- Every source returned by `search_labour_code` is a real article ID from the
  loaded corpus; unknown IDs error instead of returning empty.
- `ask_labour_code` runs the same 0.54 gate and returns the retriever's article
  IDs, never the model's.
- Tool descriptions tell the host model *when* to use each one and that it must
  cite `citation` verbatim.
- Results carry a short "not legal advice / edition valid to X" note in the tool
  output, because the host's UI will not show our disclaimer.

**Acceptance:** `stdio` server answers all four tools in a local MCP client;
tests cover schema, unknown article, empty query, and refusal.

## Phase 3 — Remote MCP

**Status 2026-10-30: shipped except deploy verification.** `/mcp` is served by a
raw ASGI router (not `app.mount`, which 307s `/mcp` to `/mcp/` and breaks clients
that will not follow a redirect on POST). Bearer auth via `MCP_TOKEN`, shared
per-IP window and daily budget, `401` without the token, and `npx mcp-remote`
instructions in the README. Not yet verified against the public deployment
because that needs the Railway env vars set.


- Mount Streamable HTTP MCP at `/mcp` on the existing FastAPI app, same image and
  Railway service. `/health` gains `mcp: true` and the tool list.
- Bearer token via `MCP_TOKEN`; per-token and per-IP limits reuse `ratelimit.py`;
  daily budget unchanged.
- Connection docs for Claude (custom connector), ChatGPT (developer mode), and
  OpenCode, with copy-paste JSON.
- Privacy note: no query text retained; logs carry tool name, latency, gate
  outcome, cost.

**Acceptance:** from a clean machine, connect with the documented steps and run
three questions including one that must be refused.

## Phase 4 — Launch (1–2 days)

- Landing section: "Use it inside your own AI" with the connector JSON and a
  30-second GIF.
- README: MCP section, tool table, generation-eval table, updated limitations.
- CHANGELOG entry; keep the V1 story intact and label this V1.1.
- Cost model published: one Voyage embed + one rerank + one generation per
  question; state the measured cost per 1,000 questions.

## Out of scope for this MVP

OAuth and paid tiers, other codes (Civil, Civil Procedure), court practice
(LITEKO), historical editions per date, multi-tenant storage, response caching,
fine-tuning, an EU-law corpus. Each is a plausible V2; none is needed to prove
that the connector is useful.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Corpus expires 2026-10-31 | Wrong-law answers | Task 1.1 before any promotion |
| "OpenAI is best at Lithuanian" may be false | Credibility | Task 1.3 before repeating the claim; keep `LLM_PROVIDER` switchable |
| Host model ignores retrieved text and answers from memory | Hallucinated law | Retrieval-first tool descriptions; `ask_labour_code` for grounded prose; cite IDs from the retriever |
| ChatGPT connector requires OAuth for listing | Blocks ChatGPT distribution | MVP targets developer mode; OAuth is a follow-up with a real user asking for it |
| Voyage is a hard runtime dependency | Outage = no retrieval | Health check covers it; state it in docs |
| Public token abuse | Cost | Daily budget already exists; add per-token limit in Phase 3 |

## Sequence

| Phase | Work | Effort | Blocks |
|---|---|---|---|
| 0 | Provider switch | done | — |
| 1.1 | Corpus refresh | 1 day | Launch |
| 1.2 | Serving = measurement | 0.5 day | Republishing numbers |
| 1.3 | Generation benchmark | 1–2 days | The OpenAI claim |
| 2 | MCP core + stdio | 2–3 days | Phase 3 |
| 3 | Remote MCP + auth | 2–3 days | Phase 4 |
| 4 | Launch polish | 1–2 days | — |

Two weeks of focused work, with 1.1 first because it is the only item whose
deadline is external.
