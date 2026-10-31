"""Check that every act being served is still in force on e-seimas.

Why this exists: the DOCX export of a repealed act still contains the old text
and no "negalioja" marker, so the ingest guard cannot read the status from the
document. 35 repealed regulations were once served as current law because of
that gap. This script is the standing guard:

    python check_act_status.py              # verify against the snapshot
    python check_act_status.py --max-age 30 # also fail if the snapshot is stale

`data/act_status.json` is refreshed by sweeping each act's e-seimas page
(`/portal/legalAct/lt/TAD/{id}`) and recording NEGALIOJA + its date. The sweep
needs a browser because e-seimas refuses non-browser clients, so refreshing is a
manual/CI-browser step; verifying is not.

Exit code is non-zero when something is wrong, so CI and scheduled jobs can use
it without parsing output.
"""

import json
import sys

from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
STATUS = ROOT / "data" / "act_status.json"
SOURCES = ROOT / "data" / "sources.json"
REPEALED = ROOT / "data" / "repealed_ids.json"

SKIP_PREFIX = ("vdi-faq", "sadm-faq", "kt-", "committee-", "seimas-", "tap-")


def indexed_acts(records):
    """Act ids actually being served, excluding explanations and editorial data."""
    out = []
    for record in records:
        act_id = record.get("act_id") or ""
        if act_id in ("vdi-faq", "sadm-faq") or act_id.startswith(SKIP_PREFIX):
            continue
        if record["source"].startswith(("Direktyva", "EŽTT", "Seimo", "Sodra")):
            continue
        if act_id and act_id not in out:
            out.append(act_id)
    return out


def main(argv=None):
    argv = argv or sys.argv[1:]
    snapshot = json.loads(STATUS.read_text(encoding="utf-8"))
    records = json.loads(SOURCES.read_text(encoding="utf-8"))
    checked = snapshot["acts"]
    checked_at = date.fromisoformat(snapshot["checked_at"])

    serving = indexed_acts(records)
    repealed = {i for i, s in checked.items() if s["state"] == "repealed"}
    unrecorded = [i for i in serving if i not in checked]
    bad = [i for i in serving if i in repealed]
    unexplained = sorted(set(checked) - set(serving))

    problems = []
    if bad:
        problems.append(f"serving repealed acts: {bad}")
    if unrecorded:
        problems.append(f"acts with no recorded status: {unrecorded}")

    if REPEALED.exists():
        recorded = json.loads(REPEALED.read_text(encoding="utf-8"))
        still = sorted(set(recorded) & set(serving))
        if still:
            problems.append(f"repealed_ids.json lists served acts: {still}")

    age = (date.today() - checked_at).days
    if "--max-age" in argv:
        limit = int(argv[argv.index("--max-age") + 1])
        if age > limit:
            problems.append(f"status snapshot is {age} days old (limit {limit})")

    print(f"acts served: {len(serving)}")
    print(f"statuses recorded: {len(checked)} (checked {checked_at}, {age} days ago)")
    print(f"repealed in snapshot: {len(repealed)}")
    if unexplained:
        print(f"recorded but no longer served: {len(unexplained)} (harmless)")
    for problem in problems:
        print(f"FAIL: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
