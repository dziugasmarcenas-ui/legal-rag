# SPRINT.md — 20-hour build sprint, legal-rag

Read this before writing any code. Written 2026-08-20 after an audit of the actual repo. Revised once. **No further planning documents.**

## Ground truth (audited, not assumed)

`~/legal-rag` as of 2026-08-20:

- `ingest.py` — 106 lines, procedural, Voyage `voyage-3` embeddings, hand-written cosine similarity, **top-1** retrieval, one hardcoded question, `0.5` confidence threshold, Claude Haiku for the cited answer.
- `corpus/` — **5 `.txt` files, 1,184 words.** English *paraphrases*, not the Darbo kodeksas. `find_article()` takes the last word of line 2, so "Articles 126-128" becomes article id `"126-128"`.
- `scratch/` — 4 learning scripts. `venv/` — populated.
- Nothing modified since 2026-06-29.

**Does not exist:** git repo (zero commits), deployment, AWS, Docker, FastAPI, any endpoint, persisted embeddings, eval set, eval runner, tests.

Prior plans were priced against a system that does not exist. The "deployed on AWS" story came from `Kilo/Session_Handoff_AWS_Decision.md`, which records deployment as an **open decision**, not a completed step. Nothing enters the README, the application, or the demo video that has not been run and observed during this sprint.

## The corpus problem

Recall@3 over 5 chunks is trivially ~100%. There is no retrieval problem to solve, no failure to analyse, no improvement story. **The 5-file corpus is fatal to the point of the sprint.**

Source the real consolidated Darbo kodeksas from e-TAR (act `XII-2603`).

**Priority order — correct ground truth beats corpus size:**

> ~250 current articles cleanly parsed > 150 cleanly parsed > 60–80 coherent articles from whole chapters > hundreds of malformed records.

If the parser is still fighting at hour 4.25, take **coherent whole chapters** — contract formation, working time, rest and leave, termination, family protections — not a random truncation. README then says: "Current corpus covers X articles from Y sections of the Lithuanian Labour Code."

**Pin the edition.** Read the consolidated-edition validity dates **off the document you actually download**. Do not hardcode dates quoted by any chatbot, including the ones in this file's revision history. Every record carries:

```json
{
  "article": "57",
  "title": "...",
  "text": "...",
  "source": "Lietuvos Respublikos darbo kodeksas",
  "act_number": "XII-2603",
  "edition_from": "YYYY-MM-DD",
  "edition_to": "YYYY-MM-DD"
}
```

README says the system answers against **that edition**, not "Lithuanian law" generically. Otherwise the benchmark silently rots when the law changes.

## Hour plan

| Hours | Task | Done when |
|---|---|---|
| 0–0.25 | `git init`, `.gitignore` (venv, `.DS_Store`, `.env`), commit, push | repo live on github.com/dziugasmarcenas-ui |
| 0.25–0.75 | Freeze scope into README stub. No new feature ideas after this line | criteria committed |
| 0.75–4.25 | Real corpus: fetch + parse into article records with edition metadata | **Gate A passes** |
| 4.25–6.25 | Article chunking + persist embeddings (numpy `.npy` + JSON sidecar — **do not** yak-shave sqlite-vec) | re-runs without re-embedding |
| 6.25–7.5 | Refactor into functions; top-**k** retrieval; inspectable with no LLM call | **Gate B passes** |
| 7.5–9 | FastAPI `POST /chat` + `GET /health` | local `curl` returns `{answer, sources, confidence}` |
| 9–11.5 | Golden set: 30 questions, manually verified, ~5 unanswerable | **Gate C passes** |
| 11.5–13.5 | Eval runner — two separate benchmarks (below). Run baseline. **Record the real number, however bad** | `results_baseline.md` committed |
| 13.5–15.5 | Failure analysis → categorise → **one** justified change → rerun the frozen set | before/after table |
| 15.5–16 | Threshold sweep table | operating point chosen on evidence |
| 16–17.5 | Dockerfile + deploy to **Railway** | **Gate D passes** |
| 17.5–18.5 | README: problem, diagram, chunking rationale, methodology, before/after, limitations | stranger gets it in 2 min |
| 18.5–19.25 | Self-interrogation, no AI open (list below) | every question answered aloud |
| 19.25–20 | Demo video, then submit ElevenLabs | submitted |

**Record the demo video immediately after the interrogation block, while the answers are hot.** The video is the artifact of the understanding, not a separate task — if you can pass 18.5–19.25 you can record 19.25–20 in one or two takes.

### Deploy target: Railway. Decision closed.

Railway has a first-party FastAPI path from GitHub and picks up a Dockerfile automatically; GitHub is already a deliverable by hour 0.25. Fly is equally viable and that is exactly why the choice is not worth re-opening inside a time-boxed sprint. AWS Lambda is out — no prior experience, and your own handoff doc priced it at 3–5+ hours for a first-timer.

## Stage gates

A gate that fails means **stop and fix**, not proceed. "Claude Code said it finished" is not a gate.

### Gate A — corpus (before embedding anything)
```
[ ] article IDs unique
[ ] no empty article text
[ ] 10 random articles spot-checked against the official source
[ ] known articles (57, 126, ...) parse correctly
[ ] no navigation / footer / cookie-banner garbage in text
[ ] edition dates recorded, read off the source document
```

### Gate B — retrieval (before building the API)
```
[ ] arbitrary query accepted, nothing hardcoded
[ ] returns top-k, ordered
[ ] each result carries article + score + text
[ ] retrieval inspectable without calling Claude
```
You must be able to run `question → RETRIEVAL ONLY → [57, 59, 61]` with no LLM tokens spent. Retrieval quality and answer quality are different failures and must be measurable separately.

### Gate C — golden set (before producing any metric)
```
[ ] every expected article manually verified by you
[ ] set frozen before tuning; any post-freeze change is noted in the README
[ ] answerable and unanswerable questions clearly separated
[ ] wording resembles how a real person asks, not statute language
```
This is the integrity of the whole project. A golden set you tuned against is not a benchmark.

### Gate D — deployment
"Railway says deployed" is not done. From a machine that is not your laptop:
```bash
curl https://<url>/health
curl -X POST https://<url>/chat -H 'Content-Type: application/json' -d '{"question":"..."}'
```
Both must return correctly.

## Two benchmarks, not one accuracy number

**Retrieval benchmark** (answerable questions only): Recall@1, Recall@3, Recall@5.

**Abstention benchmark** (both sets): correct refusal rate on unanswerable, **false refusal rate on answerable**.

Mixing these produces one muddy number that tells an interviewer nothing about what failed. With ~5 unanswerables, say so: "the refusal benchmark is exploratory — sample size is five."

## The 0.5 threshold is not sacred

It was picked arbitrarily in the toy script. Once the eval set exists, treat it as a tunable operating point. Re-use the scores you already computed — this is a loop, not a re-run, ~20 minutes:

| Threshold | Unsupported correctly refused | Answerable falsely refused |
|---|---|---|
| 0.40 | | |
| 0.50 | | |
| 0.60 | | |

Do not spend hours optimising. Do produce the table.

## Cut order, if time explodes

1. Any frontend beyond a `curl` example
2. Golden set 30 → 20 questions
3. Logging beyond stdout
4. A second retrieval experiment
5. README polish

**Never cut:** real corpus → frozen verified golden set → measured baseline → one failure fix → deployment → being able to explain it.

**The 20-hour cap is hard.** At hour 20 you submit what is true at hour 20.

## The working rule

AI is the pair programmer, not the author. Delegate freely: Dockerfile, FastAPI scaffolding, argument parsing, README formatting.

Type these yourself, and be able to rewrite them from a blank page tomorrow:

- the article parser
- the retrieval function
- cosine similarity and top-k selection
- the eval runner and the Recall@k calculation
- the confidence gate

## Self-interrogation (hour 18.5, no AI open)

**Retrieval** — what an embedding is; why cosine not Euclidean; what top-k means; why article-level chunks for statute text; what Recall@3 measures and what it misses; retrieval failure vs generation failure.

**RAG** — why not put the whole code in context; why not fine-tune; how the confidence gate works and why that operating point; how a citation binds to a source chunk rather than being generated.

**Software** — the request path from HTTP in to cited answer out; where credentials live; what happens when the model API 500s; how the container builds and deploys; where logs go.

**Evaluation** — why your golden set is trustworthy; what could contaminate it; why repeatedly tuning against one frozen set overfits; what metric you would add next.

## The story this project tells

Not "look, I know RAG." This:

> I inherited my own crude prototype, audited what was actually there, found my assumptions about both the corpus and the infrastructure were wrong, replaced five hand-written English summaries with versioned primary-source law, froze a manually verified golden set before tuning, measured retrieval, diagnosed a failure, fixed it, deployed it, and can explain the whole path.

The audit is part of the story, not something to hide. When asked what went wrong:

> My first prototype ran on five hand-written English summaries, which made retrieval look far better than it was. Preparing it for real evaluation, I realised that wasn't a meaningful benchmark. I replaced it with the actual consolidated Labour Code and froze a verified golden set before tuning anything.

That is more credible than pretending v1 was sophisticated.

## Definition of done

A stranger opens a URL, asks a Lithuanian employment-law question, gets a cited answer or an honest refusal, and reads a public README with a measured before/after retrieval table, a separate abstention result, an architecture diagram, and the corpus edition stated — and you can defend every line of the retrieval and eval code unaided.

Nothing beyond that list ships this weekend.
