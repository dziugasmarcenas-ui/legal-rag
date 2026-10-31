"""Per-source retrieval evaluation.

The Code and the delegated acts are measured. KT rulings, ECHR judgments,
committee conclusions, EU directives and Seimas drafts are not — so a regression
in any of those would be invisible on /status.

Each question names the source family that should answer it; the metric is
whether a chunk from that family appears in the served sources, and whether a
distinctive answer term is present in the returned text.

    python eval/run_source_specific_eval.py
"""

import json
import sys

from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import retrieval

SET = ROOT / "eval" / "source_specific_set.json"
OUT = ROOT / "eval" / "results_source_specific.json"


def main():
    entries = json.loads(SET.read_text(encoding="utf-8"))
    rows = []
    by_family = defaultdict(lambda: {"hits": 0, "total": 0, "terms": 0, "scored": 0})

    for entry in entries:
        results = retrieval.retrieve(entry["question"], k=3)
        delegated = [r for r in results if not r.get("article")]
        sources = [r["source"] for r in delegated]
        hit = any(entry["expected"] in (s or "") for s in sources)
        text = " ".join(r["text"].lower() for r in delegated)
        term_hit = None if not entry.get("expect") else entry["expect"].lower() in text

        family = by_family[entry["family"]]
        family["total"] += 1
        family["hits"] += hit
        if term_hit is not None:
            family["scored"] += 1
            family["terms"] += term_hit

        rows.append({
            "id": entry["id"],
            "family": entry["family"],
            "question": entry["question"],
            "expected": entry["expected"],
            "sources": sources,
            "hit": hit,
            "expect": entry.get("expect"),
            "term_hit": term_hit,
        })
        print(f"  {'hit ' if hit else 'MISS'} {entry['family']:<18} {entry['question'][:52]}")
        print(f"        -> {sources}")

    hits = sum(1 for r in rows if r["hit"])
    scored = [r for r in rows if r["term_hit"] is not None]
    terms = sum(1 for r in scored if r["term_hit"])

    print("\nby family:")
    summary_families = {}
    for name, f in sorted(by_family.items()):
        rate = f["hits"] / f["total"] if f["total"] else 0.0
        term_rate = f["terms"] / f["scored"] if f["scored"] else 0.0
        summary_families[name] = {
            "hits": f["hits"], "total": f["total"], "hit_rate": round(rate, 3),
            "term_hits": f["terms"], "term_scored": f["scored"],
            "term_rate": round(term_rate, 3),
        }
        print(f"  {name:<18} {f['hits']}/{f['total']} = {rate:.3f} "
              f"(answer term {f['terms']}/{f['scored']})")

    summary = {
        "hits": hits,
        "total": len(rows),
        "hit_rate": round(hits / len(rows), 3),
        "term_hits": terms,
        "term_total": len(scored),
        "term_rate": round(terms / len(scored), 3) if scored else 0.0,
        "families": summary_families,
    }
    print(f"\nsource-family hit rate: {hits}/{len(rows)} = {summary['hit_rate']:.3f}")
    print(f"answer-bearing chunk rate: {terms}/{len(scored)} = {summary['term_rate']:.3f}")

    OUT.write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
