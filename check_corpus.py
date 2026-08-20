"""Gate A: verify the parsed corpus before anything gets embedded.

Runs the checks that can be automated and prints a random sample for the
manual spot-check against e-TAR. Exits non-zero if any automated check fails,
so this cannot be "passed" by not looking at the output.
"""

import json
import random
import sys

from pathlib import Path

from parse_corpus import ANNOTATIONS, CITATION, EDITION_FROM, EDITION_TO, OUT

EXPECTED_COUNT = 257
SPOT_CHECK_SAMPLE = 10
SEED = 20260820

failures = []


def check(name, passed, detail=""):
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {name}" + (f" -- {detail}" if detail else ""))
    if not passed:
        failures.append(name)


articles = json.loads(Path(OUT).read_text(encoding="utf-8"))

# --- count and reconciliation ------------------------------------------------
check("article count is 257", len(articles) == EXPECTED_COUNT, f"got {len(articles)}")

identifiers = [a["article"] for a in articles]
numbered = sorted(int(i) for i in identifiers if "-" not in i)
gaps = [n for n in range(1, max(numbered) + 1) if n not in numbered]
check(
    "numbering reconciles: 1-260 minus repealed 85-88, plus 72-1",
    max(numbered) == 260 and gaps == [85, 86, 87, 88] and "72-1" in identifiers,
    f"max={max(numbered)} gaps={gaps}",
)

# --- Gate A: article IDs unique ----------------------------------------------
duplicates = {i for i in identifiers if identifiers.count(i) > 1}
check("article IDs unique", not duplicates, f"duplicates: {sorted(duplicates)}")

# --- Gate A: no empty article text -------------------------------------------
empty = [a["article"] for a in articles if not a["text"].strip()]
check("no empty article text", not empty, f"empty: {empty}")

shortest = min(articles, key=lambda a: len(a["text"]))
print(
    f"       shortest article is {shortest['article']} "
    f"({len(shortest['text'])} chars): {shortest['text'][:70]!r}"
)

# --- Gate A: no garbage in text ----------------------------------------------
polluted = []
for a in articles:
    for line in a["text"].split("\n"):
        if line in ANNOTATIONS or CITATION.match(line):
            polluted.append((a["article"], line))
            break
check("no amendment annotations in text", not polluted, f"{polluted[:3]}")

structural = [
    a["article"]
    for a in articles
    for line in a["text"].split("\n")
    if line and not any(c.islower() for c in line)
]
check("no part/chapter headers in text", not structural, f"{structural[:5]}")

# --- Gate A: known articles parse correctly ----------------------------------
by_id = {a["article"]: a for a in articles}
for known in ("57", "126", "72-1"):
    present = known in by_id
    check(f"known article {known} present", present)
    if present:
        a = by_id[known]
        print(f"       {known}: {a['title'][:78]}")
        print(f"       cited as: {a['citation']}  |  {len(a['text'])} chars of text")

# --- Gate A: edition dates recorded ------------------------------------------
dated = all(
    a["edition_from"] == EDITION_FROM and a["edition_to"] == EDITION_TO
    for a in articles
)
check("every record carries edition dates", dated, f"{EDITION_FROM} to {EDITION_TO}")

# --- manual spot-check sample ------------------------------------------------
print("\n" + "=" * 78)
print(f"MANUAL SPOT-CHECK -- verify these {SPOT_CHECK_SAMPLE} against e-TAR yourself")
print("=" * 78)
random.seed(SEED)
for a in random.sample(articles, SPOT_CHECK_SAMPLE):
    first = a["text"].split("\n")[0]
    print(f"\nArticle {a['citation']}  ({len(a['text'])} chars)")
    print(f"  title: {a['title']}")
    print(f"  opens: {first[:150]}")

print("\n" + "=" * 78)
if failures:
    print(f"GATE A FAILED -- {len(failures)} check(s): {failures}")
    sys.exit(1)
print("GATE A: all automated checks passed.")
print("Still required by SPRINT.md: your manual spot-check of the 10 above.")
