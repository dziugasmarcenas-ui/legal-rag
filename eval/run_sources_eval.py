"""Does the delegated-act index actually answer the questions it exists for?

The frozen Code benchmark cannot measure this: those questions have Labour Code
answers. These questions are about rules that live in the implementing acts, so
the metric is "is the right act among the delegated results", not "is article N
first".

    python eval/run_sources_eval.py
"""

import json
import sys

from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import retrieval

SET = ROOT / "eval" / "sources_set.json"


def main():
    entries = json.loads(SET.read_text(encoding="utf-8"))
    hits, rows = 0, []

    for entry in entries:
        results = retrieval.retrieve(entry["question"], k=3)
        delegated = [r for r in results if not r.get("article")]
        sources = [r["source"] for r in delegated]
        hit = any(entry["expected"] in (s or "") for s in sources)
        hits += hit
        # Act-level hits flatter a system that retrieved the right law and the
        # wrong provision. Where the answer has a distinctive term, require it.
        text = " ".join(r["text"].lower() for r in delegated)
        term_hit = None if not entry.get("expect") else entry["expect"].lower() in text
        rows.append({
            "id": entry["id"],
            "question": entry["question"],
            "expected": entry["expected"],
            "delegated": sources,
            "top": delegated[0]["citation"] if delegated else None,
            "hit": hit,
            "expect": entry.get("expect"),
            "term_hit": term_hit,
        })
        print(f"  {'hit ' if hit else 'MISS'} q{entry['id']:>2}  {entry['question'][:58]}")
        print(f"        -> {sources}")

    total = len(entries)
    scored = [r for r in rows if r["term_hit"] is not None]
    terms = sum(1 for r in scored if r["term_hit"])
    print(f"\ndelegated-act hit rate (top {retrieval.SOURCE_SHOWN}): "
          f"{hits}/{total} = {hits / total:.3f}")
    print(f"answer-bearing chunk rate: {terms}/{len(scored)} = {terms / len(scored):.3f}")

    (ROOT / "eval" / "results_sources.json").write_text(
        json.dumps({"summary": {"hits": hits, "total": total,
                                "hit_rate": round(hits / total, 3),
                                "term_hits": terms, "term_total": len(scored),
                                "term_rate": round(terms / len(scored), 3)},
                    "rows": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
