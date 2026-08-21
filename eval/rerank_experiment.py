"""Experiment 1: rerank the existing top-5 candidates.

Hypothesis, from the hour-13.5 failure analysis: retrieval usually reaches the
right semantic neighbourhood but loses the qualifier that decides which article
inside it governs -- who is acting, why, which subtype. Five of the seven
Recall@1 failures look like that, and Recall@5 (0.920) is far above Recall@1
(0.720), which says candidate generation is strong and ordering is weak.

EXACTLY ONE THING CHANGES: the ordering of the same five candidates.
The corpus, the chunking, the embeddings, the golden set and its labels are
all untouched, and the candidates themselves come from the cached baseline
retrieval rather than being re-retrieved.

Recall@5 is therefore an invariant: reordering five items cannot change whether
the correct article is among them. If it moves, something is wrong and this
script says so.
"""

import json
import sys

from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import voyageai

import config
import metrics

BASELINE = ROOT / "eval" / "results_raw.json"
OUT = ROOT / "eval" / "results_rerank.json"
ARTICLES = ROOT / "data" / "articles.json"
MODELS = ["rerank-2.5", "rerank-2", "rerank-2-lite"]


def document(article):
    """Same representation the corpus was embedded with, so the reranker sees
    what the retriever saw -- not a different view of the article."""
    return article["title"] + "\n" + article["text"]


def main():
    payload = json.loads(BASELINE.read_text(encoding="utf-8"))
    baseline = payload["results"]
    A = {a["article"]: a for a in json.loads(ARTICLES.read_text(encoding="utf-8"))}
    client = voyageai.Client(api_key=config.require("VOYAGE_API_KEY"))

    model = None
    for candidate in MODELS:
        try:
            client.rerank("test", ["a", "b"], model=candidate, top_k=1)
            model = candidate
            break
        except Exception as error:
            print(f"  {candidate}: unavailable ({type(error).__name__})")
    if model is None:
        sys.exit("no reranking model available")
    print(f"reranking with {model}\n")

    reranked = []
    for r in baseline:
        ids = r["retrieved"]
        docs = [document(A[i]) for i in ids]
        result = client.rerank(r["question"], docs, model=model)
        order = [ids[item.index] for item in result.results]
        scores = [round(float(item.relevance_score), 6) for item in result.results]
        reranked.append({**r, "retrieved": order, "rerank_scores": scores,
                         "baseline_retrieved": ids})

    OUT.write_text(json.dumps({"model": model, "key": payload["key"],
                               "results": reranked}, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    base_ans = [r for r in baseline if r["answerable"]]
    rr_ans = [r for r in reranked if r["answerable"]]

    print("=" * 66)
    print("RETRIEVAL BENCHMARK -- same 25 answerable questions, same candidates")
    print("=" * 66)
    print(f"  {'metric':<10} {'baseline':>10} {'reranked':>10} {'change':>10}")
    for k in (1, 3, 5):
        b = metrics.recall_at_k(base_ans, k)
        a = metrics.recall_at_k(rr_ans, k)
        print(f"  Recall@{k:<3} {b:>10.3f} {a:>10.3f} {a - b:>+10.3f}")

    b5, a5 = metrics.recall_at_k(base_ans, 5), metrics.recall_at_k(rr_ans, 5)
    print()
    if abs(b5 - a5) > 1e-9:
        print("  !! Recall@5 MOVED. Reordering five items cannot do that.")
        print("     The experiment changed more than the ordering -- do not report it.")
    else:
        print("  Recall@5 unchanged, as it must be: the candidate set is identical.")

    def rank_of(r):
        return next((i + 1 for i, a in enumerate(r["retrieved"]) if a in r["expected"]), None)

    print()
    print("  per-question rank of the correct article:")
    moved = 0
    for b, a in zip(sorted(base_ans, key=lambda x: x["id"]),
                    sorted(rr_ans, key=lambda x: x["id"])):
        rb, ra = rank_of(b), rank_of(a)
        if rb == ra:
            continue
        moved += 1
        arrow = "improved" if (ra or 99) < (rb or 99) else "REGRESSED"
        print(f"    q{b['id']:>2}  {str(rb or 'miss'):>4} -> {str(ra or 'miss'):<4} {arrow}")
    print(f"\n  {moved} of {len(base_ans)} questions changed rank")
    print("\n  NOTE: abstention is not re-reported. The gate reads a cosine score,")
    print("  and rerank relevance is a different scale -- comparing them would be")
    print("  a second change smuggled into a one-change experiment.")


if __name__ == "__main__":
    main()
