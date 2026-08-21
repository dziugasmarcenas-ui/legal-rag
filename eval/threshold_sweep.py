"""Hour 15.5: choose the abstention operating point on evidence.

The baseline sweep showed absolute cosine similarity is a weak confidence
signal -- the answerable and unanswerable ranges overlap completely. Now that
the served system reranks with a cross-encoder, there is a second candidate
signal available, and the honest thing is to sweep both and compare.

Reads cached scores only. No API calls, no re-retrieval.
"""

import json
import sys

from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import metrics

BASE = json.loads((ROOT / "eval" / "results_raw.json").read_text(encoding="utf-8"))["results"]
RR = json.loads((ROOT / "eval" / "results_rerank.json").read_text(encoding="utf-8"))["results"]


def band(results, key):
    tops = [max(r[key]) for r in results]
    return min(tops), max(tops)


def sweep(results, key, thresholds, label):
    ans = [r for r in results if r["answerable"]]
    una = [r for r in results if not r["answerable"]]
    lo_a, hi_a = band(ans, key)
    lo_u, hi_u = band(una, key)

    print(f"\n{'=' * 68}")
    print(f"{label}   (signal: {key})")
    print("=" * 68)
    print(f"  answerable   best-score range : {lo_a:.4f} .. {hi_a:.4f}   n={len(ans)}")
    print(f"  unanswerable best-score range : {lo_u:.4f} .. {hi_u:.4f}   n={len(una)}")
    separated = lo_a > hi_u
    print(f"  cleanly separable by a single threshold: {'YES' if separated else 'NO'}"
          + ("" if separated else f"  (overlap {max(lo_a, lo_u):.4f}..{min(hi_a, hi_u):.4f})"))
    print()
    print(f"  {'thresh':>7} {'unansw. refused':>18} {'answerable falsely refused':>28}")
    best = None
    for th in thresholds:
        c = metrics.correct_refusal_rate(una, th, key)
        f = metrics.false_refusal_rate(ans, th, key)
        print(f"  {th:>7.2f}   {c:>6.3f} ({round(c*len(una))}/{len(una)})"
              f"          {f:>10.3f} ({round(f*len(ans))}/{len(ans)})")
        # a simple, stated objective: catch unsupported queries while rarely
        # refusing answerable ones. Stated so the choice is not post-hoc.
        score = c - f
        if best is None or score > best[0]:
            best = (score, th, c, f)
    print(f"\n  best on (correct refusal - false refusal): threshold {best[1]:.2f}"
          f"  ->  {best[2]:.3f} correct, {best[3]:.3f} false")
    return best


cos = sweep(BASE, "scores", [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60], "COSINE GATE (baseline)")
rrk = sweep(RR, "rerank_scores", [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80],
            "RERANKER GATE (served system)")

print(f"\n{'=' * 68}")
print("COMPARISON")
print("=" * 68)
print(f"  cosine    best: threshold {cos[1]:.2f}  correct {cos[2]:.3f}  false {cos[3]:.3f}")
print(f"  reranker  best: threshold {rrk[1]:.2f}  correct {rrk[2]:.3f}  false {rrk[3]:.3f}")
print("\n  Reranker relevance is NOT a calibrated probability. It is a different")
print("  score on a different scale, evaluated here empirically against the same")
print("  frozen benchmark rather than assumed to mean anything in particular.")
