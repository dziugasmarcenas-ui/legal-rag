"""Run the frozen golden set through retrieval and cache the raw results.

    python eval/run_eval.py            use cache if valid, else retrieve
    python eval/run_eval.py --refresh  force re-retrieval

Retrieval runs once and every score is cached. The threshold sweep and any
later metric read that cache, so re-measuring costs nothing and every number
in the report comes from the same set of retrievals.

Refuses to run against a golden set that is unfrozen or has changed since the
freeze -- a benchmark you edited mid-experiment is not a benchmark.
"""

import json
import sys

from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import numpy as np
import voyageai

import config
import metrics
import retrieval

GOLDEN = ROOT / "eval" / "golden_set.json"
FROZEN = ROOT / "eval" / "FROZEN"
CACHE = ROOT / "eval" / "results_raw.json"
TOP_N = 5


def load_frozen_golden():
    if not FROZEN.exists():
        sys.exit("golden set is not frozen. Run: python check_goldenset.py --freeze")
    entries = json.loads(GOLDEN.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT))
    from check_goldenset import content_hash

    record = json.loads(FROZEN.read_text(encoding="utf-8"))
    if content_hash(entries) != record["content_hash"]:
        sys.exit(
            "golden set has CHANGED since it was frozen.\n"
            "Either restore it, or re-freeze and note the change in the README."
        )
    return entries, record


def cache_key(record):
    """Cache is valid only for this golden set AND this corpus."""
    return {
        "golden_hash": record["content_hash"],
        "corpus_fingerprint": retrieval.SIDECAR["corpus_fingerprint"],
        "embedding_model": retrieval.SIDECAR["model"],
    }


def retrieve_all(entries):
    """Embed every question in one batch, then score against the corpus."""
    questions = [e["question"] for e in entries]
    client = voyageai.Client(api_key=config.require("VOYAGE_API_KEY"))
    embedded = client.embed(
        questions, model=retrieval.SIDECAR["model"], input_type="query"
    )

    results = []
    for entry, vector in zip(entries, embedded.embeddings):
        query = np.array(vector, dtype=np.float32)
        scores = retrieval.cosine_similarities(query, retrieval.VECTORS)
        rows = retrieval.top_k(scores, TOP_N)
        results.append(
            {
                "id": entry["id"],
                "question": entry["question"],
                "answerable": entry["answerable"],
                "expected": entry["expected_articles"],
                "retrieved": [retrieval.ARTICLES[r]["article"] for r in rows],
                "scores": [round(float(scores[r]), 6) for r in rows],
            }
        )
    return results


def main():
    entries, record = load_frozen_golden()
    key = cache_key(record)

    cached = None
    if CACHE.exists() and "--refresh" not in sys.argv:
        payload = json.loads(CACHE.read_text(encoding="utf-8"))
        if payload.get("key") == key:
            cached = payload["results"]

    if cached is None:
        print(f"retrieving {len(entries)} questions (one batched embedding call)...")
        results = retrieve_all(entries)
        CACHE.write_text(
            json.dumps({"key": key, "results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"cached to {CACHE.relative_to(ROOT)}")
    else:
        results = cached
        print("using cached retrieval results -- no API call made")

    answerable = [r for r in results if r["answerable"]]
    unanswerable = [r for r in results if not r["answerable"]]

    print()
    print("=" * 62)
    print("RETRIEVAL BENCHMARK -- answerable questions only")
    print("=" * 62)
    print(f"  n = {len(answerable)}")
    for k in (1, 3, 5):
        value = metrics.recall_at_k(answerable, k)
        print(f"  Recall@{k}: {value:.3f}  ({round(value * len(answerable))}/{len(answerable)})")

    print()
    print("  per-question detail:")
    for r in sorted(answerable, key=lambda x: x["id"]):
        rank = next(
            (i + 1 for i, a in enumerate(r["retrieved"]) if a in r["expected"]), None
        )
        status = f"rank {rank}" if rank else "MISS    "
        print(
            f"    q{r['id']:>2}  {status}  score {r['scores'][0]:.4f}  "
            f"expected {','.join(r['expected']):<10} got {','.join(r['retrieved'][:3])}"
        )

    import gate

    print()
    print("=" * 62)
    print("ABSTENTION BENCHMARK -- both sets, at the deployed threshold")
    print("=" * 62)
    print(f"  threshold in gate.py: {gate.THRESHOLD}")
    cr = metrics.correct_refusal_rate(unanswerable, gate.THRESHOLD)
    fr = metrics.false_refusal_rate(answerable, gate.THRESHOLD)
    print(f"  unanswerable correctly refused: {cr:.3f}  "
          f"({round(cr * len(unanswerable))}/{len(unanswerable)})")
    print(f"  answerable falsely refused:     {fr:.3f}  "
          f"({round(fr * len(answerable))}/{len(answerable)})")
    print(f"  NOTE: exploratory -- only {len(unanswerable)} unanswerable questions.")

    print()
    print("=" * 62)
    print("THRESHOLD SWEEP -- reusing the same cached scores")
    print("=" * 62)
    print(f"  {'thresh':>7}  {'unansw. refused':>16}  {'answerable falsely refused':>27}")
    for threshold in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60):
        c = metrics.correct_refusal_rate(unanswerable, threshold)
        f = metrics.false_refusal_rate(answerable, threshold)
        mark = "  <-- deployed" if abs(threshold - gate.THRESHOLD) < 1e-9 else ""
        print(f"  {threshold:>7.2f}  {c:>7.3f} ({round(c*len(unanswerable))}/{len(unanswerable)})"
              f"  {f:>17.3f} ({round(f*len(answerable))}/{len(answerable)}){mark}")

    print()
    print("  top-1 score range, answerable:   "
          f"{min(r['scores'][0] for r in answerable):.4f} .. {max(r['scores'][0] for r in answerable):.4f}")
    print("  top-1 score range, unanswerable: "
          f"{min(r['scores'][0] for r in unanswerable):.4f} .. {max(r['scores'][0] for r in unanswerable):.4f}")


if __name__ == "__main__":
    main()
