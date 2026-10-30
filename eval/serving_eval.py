"""Measure the pipeline the API actually serves, not a cousin of it.

`run_eval.py` measures candidate generation: it embeds the questions in one
batch and reads the top-5 cosine neighbours. That is a useful number, but it is
not what a user gets. A user gets whatever `retrieval.retrieve()` returns, and
that function reranks a larger candidate set and returns fewer articles.

The difference is not cosmetic. Reranking only reorders what it is given, so
"the right article was ranked 4th by cosine" and "the right article was served"
are different claims. This script makes the second one measurable:

    python eval/serving_eval.py            # use the cache if it is valid
    python eval/serving_eval.py --refresh  # re-run retrieval

It calls `retrieval.retrieve(question)` with no arguments, exactly as `main.py`
does. If someone changes the served configuration, this file needs no edit and
the number moves with the product.
"""

import json
import sys

from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import gate
import metrics
import retrieval
from run_eval import load_frozen_golden

CACHE = ROOT / "eval" / "results_serving.json"


def cache_key(record):
    """A cached number is only valid for this corpus, benchmark and configuration."""
    return {
        "golden_hash": record["content_hash"],
        "corpus_fingerprint": retrieval.SIDECAR["corpus_fingerprint"],
        "embedding_model": retrieval.SIDECAR["model"],
        "rerank_model": retrieval.RERANK_MODEL,
        "candidates": retrieval.SERVED_CANDIDATES,
        "k": retrieval.SERVED_K,
    }


def load_cache(key):
    if not CACHE.exists():
        return None
    payload = json.loads(CACHE.read_text(encoding="utf-8"))
    return payload if payload.get("key") == key else None


def measure(entries):
    """Run the served pipeline once per question and keep what it returned."""
    rows = []
    for entry in entries:
        results = retrieval.retrieve(entry["question"])
        rows.append(
            {
                "id": entry["id"],
                "question": entry["question"],
                "answerable": entry["answerable"],
                "expected": entry["expected_articles"],
                "retrieved": [r["article"] for r in results],
                "citations": [r["citation"] for r in results],
                "scores": [r["rerank_score"] for r in results],
                "cosine": [r["cosine_score"] for r in results],
                "refused": not gate.should_answer(results),
            }
        )
        mark = "hit " if metrics.hit_at_k(rows[-1], retrieval.SERVED_K) else "MISS"
        print(f"  {mark} q{entry['id']:>2}  {entry['question'][:60]}")
    return rows


def report(rows):
    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]

    hit1 = metrics.recall_at_k(answerable, 1)
    hit_k = metrics.recall_at_k(answerable, retrieval.SERVED_K)
    false_refusal = metrics.false_refusal_rate(answerable, gate.THRESHOLD, key="scores")
    correct_refusal = metrics.correct_refusal_rate(
        unanswerable, gate.THRESHOLD, key="scores"
    )

    served = [r for r in rows if not r["refused"]]
    return {
        "questions": len(rows),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "candidates": retrieval.SERVED_CANDIDATES,
        "served_k": retrieval.SERVED_K,
        "served_hit1": round(hit1, 4),
        "served_hit_rate": round(hit_k, 4),
        "false_refusal_rate": round(false_refusal, 4),
        "correct_refusal_rate": round(correct_refusal, 4),
        "answered": len(served),
    }


def main(argv):
    refresh = "--refresh" in argv
    entries, record = load_frozen_golden()
    key = cache_key(record)

    payload = None if refresh else load_cache(key)
    if payload:
        print("using cached serving results (pass --refresh to re-run)")
        rows = payload["rows"]
    else:
        print(f"retrieving {len(entries)} questions through the served pipeline")
        rows = measure(entries)
        payload = {"key": key, "rows": rows}
        CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = report(rows)
    payload["summary"] = summary
    CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\nserved configuration")
    print(f"  candidates retrieved : {summary['candidates']}")
    print(f"  articles shown       : {summary['served_k']}")
    print(f"  top-1 is correct     : {summary['served_hit1']:.3f}"
          f"  ({round(summary['served_hit1'] * summary['answerable'])}/{summary['answerable']} answerable)")
    print(f"  correct in top {summary['served_k']}      : {summary['served_hit_rate']:.3f}"
          f"  ({round(summary['served_hit_rate'] * summary['answerable'])}/{summary['answerable']} answerable)")
    print(f"  false refusal rate   : {summary['false_refusal_rate']:.3f}")
    print(f"  correct refusal rate : {summary['correct_refusal_rate']:.3f} (n={summary['unanswerable']})")
    print(f"  answered             : {summary['answered']}/{summary['questions']}")
    print(f"\nwrote {CACHE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
