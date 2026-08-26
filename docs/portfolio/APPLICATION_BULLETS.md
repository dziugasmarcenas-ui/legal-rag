# Application Copy

All metrics below refer to the frozen V1 benchmark documented in the [technical README](../../README.md).

## CV bullets

- Built and deployed a bilingual RAG application over 257 primary-source Lithuanian Labour Code articles using Python, FastAPI, vector retrieval, reranking, Claude, Docker, and CI.
- Designed a frozen 30-question evaluation, diagnosed ranking failures, and improved Recall@1 from 72% to 88% and Recall@3 from 84% to 92% without changing corpus coverage.
- Added evidence-based abstention, source-linked citations, rate limiting, dependency failure handling, and documented limitations separating retrieval relevance from answerability.

## LinkedIn project description

Built and deployed a Lithuanian Labour Code RAG application that answers from 257 primary-source articles, links responses to retrieved sources, and refuses when evidence is insufficient. I replaced a misleading five-document prototype with a versioned corpus and frozen evaluation set, diagnosed ranking failures, and improved Recall@1 from 72% to 88% through cross-encoder reranking. The public FastAPI service includes a bilingual interface, Docker deployment, CI integrity gates, rate limiting, and explicit documentation of remaining retrieval and answerability failures.

## GitHub description

Deployed Lithuanian legal RAG with primary-source citations, measured retrieval, abstention, FastAPI, Docker, CI, and an LT/EN interface.

## Role-specific framing

### Applied AI / Forward-Deployed AI

Emphasize the end-to-end path: scoping an ambiguous user problem, replacing a weak prototype, establishing evaluation, diagnosing a failure, implementing one measured intervention, deploying the result, and explaining it to non-technical users. Pair the project with client-facing and training experience.

### AI Engineer

Lead with primary-source ingestion, persisted embeddings, top-k retrieval, cross-encoder reranking, the frozen benchmark, controlled before/after metrics, confidence gating, FastAPI, Docker, CI, and explicit failure taxonomy. Be ready to trace the request path and explain why Recall@5 is a control.

### AI Enablement / Solutions Engineering

Lead with translating a complex domain into a usable bilingual tool, presenting confidence and citations clearly, controlling paid API usage, documenting limitations, and creating a demo that a non-technical stakeholder can inspect. Emphasize teaching and communication alongside implementation.

## Interview talking points

- The first prototype produced flattering metrics because the corpus was trivial; replacing it was a product-integrity decision.
- The benchmark was frozen before tuning, and every expected article was checked manually.
- The intervention followed failure analysis: high Recall@5 and lower Recall@1 indicated an ordering problem.
- Reranking cannot recover articles absent from the candidate set; two such failures remain.
- A high relevance score does not prove that an article contains enough information to answer.
- Public deployment introduced real concerns: API failures, paid-call limits, privacy, and honest health reporting.

## Claims I do not make

- The 0.54 reranker threshold is not a calibrated probability.
- The small abstention result is not held-out performance.
- The application does not cover all Lithuanian employment law or provide legal advice.
- A cited answer is not automatically proven faithful sentence by sentence.
- This portfolio project is not presented as professional production-AI tenure.
