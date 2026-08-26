# Demo and Interview Guide

[Live application](https://legal-rag-production-fac6.up.railway.app) · [Technical README](../../README.md)

The generated wording can vary. Verify both queries against the live deployment immediately before recording; describe the behavior and evidence rather than memorizing the exact prose.

## 90-second recording script

### 0:00–0:10 — Problem and scope

> This is a deployed RAG assistant over a pinned edition of the Lithuanian Labour Code. It answers from 257 primary-source articles, cites the article it used, and refuses when the retrieved evidence is not strong enough.

Show the header, edition dates, and LT/EN control.

### 0:10–0:45 — Grounded answer

Submit:

> Kiek dienų kasmetinių atostogų man priklauso per metus?

> The question is embedded, the system retrieves five candidate articles, and a cross-encoder reranks them. Here the confidence is above the 0.54 gate, so the model answers using only the retrieved text. The citation links directly to article 126 in the source cards.

Show the answer, citation, confidence bar, and article 126 card. Do not quote a score until the current run displays it.

### 0:45–1:10 — Honest refusal

Submit:

> Kiek pensijos susikaupsiu per 10 metų?

> Pension accumulation is outside this Labour Code corpus. Instead of inventing an answer, the system refuses and still shows the articles it considered, so the decision remains inspectable.

### 1:10–1:30 — Measured result

> I froze and manually verified a 30-question benchmark before tuning. Failure analysis showed that ordering was the main problem, so I reranked the same five candidates. Recall at one improved from 72 to 88 percent and Recall at three from 84 to 92 percent, while Recall at five stayed at 92 percent as expected. The README documents the method, remaining failures, deployment, and CI.

End on the README’s “Results at a glance” table.

## Live check before recording

1. Open the live application in a signed-out or private browser window.
2. Confirm the consolidated-edition dates are visible.
3. Run the annual-leave question and confirm it is answered with article 126 present.
4. Run the pension question and confirm it is refused.
5. Refresh once to confirm the application reloads cleanly.
6. Record only after both behaviors match this guide.

If an external API or Railway is unavailable, record the README and architecture as a narrated fallback. State that the live dependency is unavailable during recording; do not substitute mocked results.

## Four-minute interview walkthrough

1. **Problem:** legal answers need primary-source grounding, citations, and an explicit boundary when the corpus lacks the answer.
2. **Architecture:** pinned e-TAR edition → article parser → persisted embeddings → cosine top five → cross-encoder reranker → 0.54 confidence gate → constrained generation → retriever-attached sources.
3. **Evaluation integrity:** 30 questions were manually verified and frozen before tuning; retrieval and abstention are measured separately.
4. **Failure diagnosis:** the baseline often found the right legal neighbourhood but ranked a general article above the qualifying article.
5. **Intervention:** reranking improved Recall@1 from 0.720 to 0.880 and Recall@3 from 0.840 to 0.920; unchanged Recall@5 shows the candidate set did not change.
6. **Limitations:** two candidate-generation failures remain, missing diacritics hurt retrieval, and relevance does not guarantee answerability.
7. **Delivery:** FastAPI, Docker, Railway, CI integrity gates, rate limiting, bilingual presentation, and graceful upstream failure behavior.

## Likely interview questions

### Why article-level chunks?

Statutes already provide meaningful citation boundaries. Article-level chunks make retrieval results explainable and citations stable. The trade-off is that long articles can dilute several legal concepts into one embedding.

### What does Recall@k measure?

It measures whether the manually expected article appears in the first `k` retrieved results. It isolates retrieval from answer-writing quality and does not measure factual faithfulness of the generated prose.

### Why add reranking?

Recall@5 was already 0.920 while Recall@1 was 0.720. That gap indicated strong candidate generation but weak ordering. A cross-encoder could compare the question with each candidate more precisely without changing the corpus or embedding model.

### Why is the threshold 0.54?

It is the midpoint of the observed gap between answerable and most unanswerable development questions using reranker relevance. It is an in-sample operating point, not a probability and not a held-out performance guarantee.

### Why is relevance different from answerability?

An article can be exactly about the user’s topic but delegate the requested detail to another law. The reranker correctly marks it relevant even though the retrieved text cannot support a complete answer.
