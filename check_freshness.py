"""Fail when the corpus is older than the law.

This is deliberately *not* part of the pull-request gate. A library that is red
every day because a legal edition rolled over teaches people to ignore red; the
signal belongs in a scheduled workflow where red means "go refresh the corpus".

    python check_freshness.py            # offline: is the edition still in force?
    python check_freshness.py --online   # also: does e-TAR serve a newer edition?

The online check is the one that catches a rollover *before* the text is served
as current, which is the difference between a maintenance task and a wrong
answer.
"""

import json
import sys

from datetime import date
from pathlib import Path

import edition

ROOT = Path(__file__).parent
SIDECAR = ROOT / "embeddings" / "corpus.json"
SOURCES = ROOT / "data" / "sources.json"


def sidecar():
    if not SIDECAR.exists():
        sys.exit(f"no sidecar at {SIDECAR}; run embed_corpus.py first")
    return json.loads(SIDECAR.read_text(encoding="utf-8"))


def source_acts():
    if not SOURCES.exists():
        return []
    records = json.loads(SOURCES.read_text(encoding="utf-8"))
    by_source = {}
    for record in records:
        by_source.setdefault(record["source"], record)
    return list(by_source.values())


def check_source_editions(today):
    """Every ingested act must still be in force, and be the edition we stored."""
    stale = [r["source"] for r in source_acts() if r["valid_to"] < today.isoformat()]
    if stale:
        print(f"::error::delegated acts out of date: {stale}. Run: python ingest_sources.py --refresh")
        return 1
    return 0


def main(argv):
    record = sidecar()
    valid_to = record["edition_to"]
    today = date.today()

    if edition.is_expired(valid_to, today):
        print(
            f"::error::corpus edition expired on {valid_to}; "
            f"answers describe the law as of that date, not today. "
            f"Run: python refresh_corpus.py --write"
        )
        return 1

    print(
        f"edition {record['edition_from']} .. {valid_to} is in force "
        f"({edition.days_left(valid_to, today)} day(s) left)"
    )

    if "--online" not in argv:
        return 0

    # Imported here so the offline check has no network code path at all.
    import refresh_corpus as rc

    text = rc.docx_text(rc.download_docx(rc.edition_token(rc.fetch(rc.PORTAL))))
    start, end = rc.edition_window(text)

    if (start, end) != (record["edition_from"], valid_to):
        print(
            f"::error::e-TAR now serves {start} .. {end}, "
            f"the corpus is {record['edition_from']} .. {valid_to}. "
            f"Run: python refresh_corpus.py"
        )
        return 1

    print("e-TAR serves the same edition; nothing to refresh")

    # Delegated acts roll independently of the Code; check them too.
    if source_acts():
        import ingest_sources as ing

        for act in ing.ACTS:
            try:
                text = rc.docx_text(ing.download(act))
            except SystemExit as error:
                print(f"::error::{act['short']}: {error}")
                return 1
            window = ing.validity(act, text)
            if window is None:
                print(f"::error::{act['short']} is no longer in force")
                return 1
            stored = next(
                (r for r in source_acts() if r["source"] == act["short"]), None
            )
            if stored and stored["valid_from"] != window[0]:
                print(
                    f"::error::{act['short']} has a newer edition from {window[0]}; "
                    "stored is from " + stored["valid_from"] + ". Run: python ingest_sources.py --refresh"
                )
                return 1
        print(f"delegated acts current: {len(ing.ACTS)}")

    return check_source_editions(today)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
