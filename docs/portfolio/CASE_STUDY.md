# Case Study: Lithuanian Labour Code RAG

[Live application](https://legal-rag-production-fac6.up.railway.app) · [Technical README](../../README.md)

## The problem

Employment-law questions often sound simple—“How much annual leave do I get?” or “How much notice should my employer give me?”—but a useful answer must identify the governing legal text, distinguish similar situations, and admit when the available source does not contain the answer.

I built a retrieval-augmented application over a pinned consolidated edition of the Lithuanian Labour Code. A user asks a question in ordinary Lithuanian, the system retrieves and reranks relevant articles, and an answering model writes only from those articles. The interface attaches the retrieved sources and displays an explicit refusal when the evidence falls below the measured threshold.

This is an information-retrieval demonstration, not legal advice. It covers one edition of one code and makes that boundary visible.

## My role

I scoped the product, acquired and parsed the primary-source corpus, selected article-level chunks, generated and persisted embeddings, implemented retrieval and reranking, built the evaluation workflow, created and verified the golden set, analysed failures, selected the abstention signal, built the FastAPI service and browser interface, added rate limiting and dependency-failure behavior, containerized the service, configured CI, and deployed it publicly.

AI coding tools assisted implementation. I own the architecture, experiment design, trade-offs, measurements, and explanations, and I can trace a request from HTTP input through retrieval, reranking, confidence gating, generation, and source attachment.

## The weak first version

The first prototype used five hand-written English summaries of Lithuanian labour law, top-one retrieval, one hardcoded question, and an arbitrary confidence threshold. Recall over five documents looked impressive because the task was trivial. It was not evidence that the system could retrieve the real law.

I preserved that version in Git history, then replaced it with the consolidated Labour Code: 257 article records carrying article number, title, text, source, act number, and edition dates. Before tuning retrieval, I froze a manually verified 30-question golden set containing 25 answerable and five deliberately unanswerable questions.

That sequence mattered. Freezing the benchmark before intervention made it harder to rewrite the test around the result I wanted.

## The V1 system

The offline build parses the e-TAR source into article-level records and embeds each title plus body with `voyage-3`. Persisted vectors mean application restarts do not re-embed the law.

At request time, the question is embedded and compared with all article vectors using cosine similarity. The top five candidates are passed to `rerank-2.5`, a cross-encoder that scores each candidate jointly with the question. The highest reranker score is checked against the 0.54 operating threshold. Below that threshold, the API refuses and still returns the articles it considered. Above it, Claude Haiku receives only the retrieved articles and must cite the governing article.

The browser interface exposes this process instead of hiding it. Users see the answer or refusal, confidence relative to the gate, retrieved article titles, reranker and cosine scores, and clickable inline citations. An LT/EN switch changes presentation and answer language, but the underlying law and benchmark remain Lithuanian.

## The measured intervention

The dense-retrieval baseline achieved Recall@1 of 0.720, Recall@3 of 0.840, and Recall@5 of 0.920 on the 25 answerable questions. Seven top-one failures showed a repeated pattern: retrieval reached the correct legal neighbourhood but often ranked a general mechanism above the qualifying article that actually governed the situation.

That diagnosis suggested a ranking intervention rather than a new corpus or larger candidate pool. I reranked the same cached five candidates with the cross-encoder. Recall@1 improved from 0.720 to 0.880, and Recall@3 improved from 0.840 to 0.920. Four questions moved to rank one and none regressed.

Recall@5 remained 0.920. That unchanged result is a useful control: reordering five existing candidates cannot make a missing article appear. It confirms that the experiment improved ordering rather than silently changing candidate generation. It also exposes the two remaining failures, where the correct article never entered the top five.

## Abstention and answerability

I evaluated abstention separately from retrieval. The reranker score separated the small development set better than cosine similarity, so I selected 0.54 as the midpoint of the observed gap. It is an empirical operating point, not a calibrated probability.

The result also revealed a more important limitation. One unanswerable question about court filing procedure retrieves the correct Labour Code article with high relevance, but that article delegates the details to the Code of Civil Procedure. The article is topically relevant while still lacking the requested answer. Relevance and answerability are different problems; a relevance threshold cannot fully solve both.

## What still fails

- The abstention threshold is in-sample and only five golden-set questions are unanswerable.
- Two answerable questions are candidate-generation failures that reranking cannot repair.
- Queries without Lithuanian diacritics can retrieve worse articles.
- Article-level chunks preserve legal boundaries but can dilute long articles into one vector.
- The source is one consolidated edition of one code, without case law or related regulations.
- Generated prose still requires verification against e-TAR or a qualified professional.

These limitations remain prominent because they define what the measurements do—and do not—support.

## Delivery evidence

The application is served by FastAPI, packaged in Docker, deployed on Railway, and protected by per-IP rate limits because every answer makes paid embedding, reranking, and generation calls. GitHub Actions verifies metric logic, corpus integrity, golden-set immutability, and offline imports. The health endpoint exposes the corpus edition, threshold, models, supported languages, and usage state.

## Why this matters to an employer

This project demonstrates more than calling an LLM API. I turned a real information problem into a bounded product, replaced a misleading prototype with primary-source data, established evaluation before tuning, diagnosed a specific failure mode, chose one justified intervention, deployed the result, and documented what still fails.

That workflow maps directly to applied AI and forward-deployed work: clarify the problem, prototype quickly, measure the system rather than the demo, communicate trade-offs, handle operational constraints, and explain the result to both technical and non-technical stakeholders.
