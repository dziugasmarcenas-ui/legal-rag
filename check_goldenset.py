"""Gate C: verify the golden set before it is used to produce any metric.

Also manages the freeze. Once eval/FROZEN exists, this script reports any
later change to the questions -- so "the set was frozen before tuning" is a
checkable fact rather than a claim.

    python check_goldenset.py          verify
    python check_goldenset.py --freeze record the freeze
"""

import hashlib
import json
import sys

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
GOLDEN = ROOT / "eval" / "golden_set.json"
FROZEN = ROOT / "eval" / "FROZEN"
ARTICLES = ROOT / "data" / "articles.json"

TARGET_TOTAL = 30
MIN_UNANSWERABLE = 4
MAX_UNANSWERABLE = 7

failures = []


def check(name, passed, detail=""):
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not passed:
        failures.append(name)


def content_hash(entries):
    """Hash of the questions and their expected answers only."""
    digest = hashlib.sha256()
    for e in sorted(entries, key=lambda x: x["id"]):
        digest.update(str(e["id"]).encode())
        digest.update(e["question"].strip().encode())
        digest.update(",".join(sorted(e["expected_articles"])).encode())
        digest.update(str(e["answerable"]).encode())
    return digest.hexdigest()


entries = json.loads(GOLDEN.read_text(encoding="utf-8"))
corpus_ids = {a["article"] for a in json.loads(ARTICLES.read_text(encoding="utf-8"))}

placeholders = [e["id"] for e in entries if "EXAMPLE - DELETE ME" in e["question"]]
check("no template placeholders left", not placeholders, f"ids: {placeholders}")

check(f"{TARGET_TOTAL} questions", len(entries) == TARGET_TOTAL, f"got {len(entries)}")

ids = [e["id"] for e in entries]
check("ids unique", len(ids) == len(set(ids)))

questions = [e["question"].strip().lower() for e in entries]
dupes = {q for q in questions if questions.count(q) > 1}
check("questions unique", not dupes, f"{list(dupes)[:2]}")

unanswerable = [e for e in entries if not e["answerable"]]
check(
    f"{MIN_UNANSWERABLE}-{MAX_UNANSWERABLE} unanswerable questions",
    MIN_UNANSWERABLE <= len(unanswerable) <= MAX_UNANSWERABLE,
    f"got {len(unanswerable)}",
)

bad_answerable = [e["id"] for e in entries if e["answerable"] and not e["expected_articles"]]
check("every answerable question has expected articles", not bad_answerable, f"ids: {bad_answerable}")

bad_unanswerable = [e["id"] for e in entries if not e["answerable"] and e["expected_articles"]]
check("unanswerable questions have no expected articles", not bad_unanswerable, f"ids: {bad_unanswerable}")

unknown = sorted({a for e in entries for a in e["expected_articles"]} - corpus_ids)
check("every expected article exists in the corpus", not unknown, f"unknown: {unknown}")

unnoted = [e["id"] for e in entries if not e.get("verified_note", "").strip()]
check("every question carries a verification note", not unnoted, f"ids: {unnoted}")

# --- freeze -------------------------------------------------------------------
current = content_hash(entries)

if "--freeze" in sys.argv:
    if failures:
        sys.exit("\nrefusing to freeze a golden set that fails its checks.")
    FROZEN.write_text(
        json.dumps(
            {"frozen_at": datetime.now(timezone.utc).isoformat(),
             "content_hash": current, "count": len(entries)},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nFROZEN at {current[:16]}... -- {len(entries)} questions")
    print("Any later change to a question or its expected articles will now be reported.")
    sys.exit(0)

if FROZEN.exists():
    record = json.loads(FROZEN.read_text(encoding="utf-8"))
    unchanged = record["content_hash"] == current
    check("golden set unchanged since freeze", unchanged,
          f"frozen {record['frozen_at']}" if unchanged else "CHANGED AFTER FREEZE - must be noted in README")
else:
    print("[ -- ] not yet frozen. Run with --freeze once the 30 questions are final.")

print()
if failures:
    sys.exit(f"GATE C FAILED -- {len(failures)} check(s): {failures}")
print("GATE C: all automated checks passed.")
if FROZEN.exists():
    print("Set is frozen. Metrics may now be produced.")
else:
    print("Freeze the set before producing any metric.")
