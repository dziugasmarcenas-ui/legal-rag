"""Does lexical retrieval earn its place? Measure it or leave it out.

Compares the served pipeline (vector candidates, cross-encoder rerank) against
hybrid candidates (vector + BM25, fused by rank, same reranker, same gate) on
the frozen golden set. One variable changes: how candidates are generated.

    python eval/hybrid_experiment.py

Writes eval/results_hybrid.json. The served numbers are only changed if this
wins; a retrieval change that is not measured is a preference.
"""

import json
import sys

from pathlib import Path

import numpy as np
import voyageai

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import gate
import lexical
import metrics
import retrieval
from run_eval import load_frozen_golden

OUT = ROOT / "eval" / "results_hybrid.json"
CANDIDATES = retrieval.SERVED_CANDIDATES
SHOWN = retrieval.SERVED_K


def reranked(question, rows, client):
    documents = [r["title"] + "\n" + r["text"] for r in rows]
    ranking = client.rerank(question, documents, model=retrieval.RERANK_MODEL)
    ordered = []
    for item in ranking.results:
        record = dict(rows[item.index])
        record["rerank_score"] = float(item.relevance_score)
        ordered.append(record)
    return ordered


def main(argv=None):
    entries, _ = load_frozen_golden()
    articles = {a["article"]: a for a in retrieval.ARTICLES}
    index = lexical.build()
    client = voyageai.Client(api_key=__import__("config").require("VOYAGE_API_KEY"))

    embedded = client.embed(
        [e["question"] for e in entries], model="voyage-3", input_type="query"
    )

    rows = []
    for entry, vector in zip(entries, embedded.embeddings):
        query = np.array(vector, dtype=np.float32)
        scores = retrieval.cosine_similarities(query, retrieval.VECTORS)
        vector_ids = [retrieval.ARTICLES[r]["article"] for r in retrieval.top_k(scores, CANDIDATES)]

        lexical_ids = index.ranked(entry["question"])[:CANDIDATES]
        fused = lexical.fuse(vector_ids, lexical_ids)[:CANDIDATES]
        # Union keeps every vector candidate and only adds lexical ones, so a
        # good semantic hit cannot be displaced by a keyword match.
        union = vector_ids + [i for i in lexical_ids if i not in vector_ids][:5]

        def candidate_results(ids):
            out = []
            for identifier in ids:
                a = articles[identifier]
                out.append({
                    "article": a["article"],
                    "citation": a["citation"],
                    "title": a["title"],
                    "text": a["text"],
                    "cosine_score": float(scores[retrieval.ARTICLES.index(a)]),
                    "rerank_score": None,
                })
            return out

        base = reranked(entry["question"], candidate_results(vector_ids), client)[:SHOWN]
        hybrid = reranked(entry["question"], candidate_results(union), client)[:SHOWN]

        def row(results):
            return {
                "retrieved": [r["article"] for r in results],
                "scores": [r["rerank_score"] for r in results],
            }

        rows.append({
            "id": entry["id"],
            "answerable": entry["answerable"],
            "expected": entry["expected_articles"],
            "vector": row(base),
            "hybrid": row(hybrid),
        })
        expected = {"expected": entry["expected_articles"]}
        vh = "hit " if metrics.hit_at_k({**expected, **rows[-1]["vector"]}, 1) else "MISS"
        hh = "hit " if metrics.hit_at_k({**expected, **rows[-1]["hybrid"]}, 1) else "MISS"
        print(f"  q{entry['id']:>2}  vector {vh}  union {hh}")

    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]

    def summary(key):
        rows_for = [{"expected": r["expected"], **r[key]} for r in answerable]
        return {
            "recall@1": round(metrics.recall_at_k(rows_for, 1), 3),
            "recall@3": round(metrics.recall_at_k(rows_for, SHOWN), 3),
            "false_refusal": round(metrics.false_refusal_rate(
                [{"scores": r[key]["scores"]} for r in answerable], gate.THRESHOLD), 3),
            "correct_refusal": round(metrics.correct_refusal_rate(
                [{"scores": r[key]["scores"]} for r in unanswerable], gate.THRESHOLD), 3),
        }

    print("\nserved candidates (vector only):", summary("vector"))
    print("union candidates (vector 10 + BM25 extras):", summary("hybrid"))

    OUT.write_text(json.dumps({"summary": {"vector": summary("vector"),
                                           "hybrid": summary("hybrid")},
                               "rows": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
