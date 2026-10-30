"""Build a versioned history of the Labour Code from e-TAR.

The corpus is not one text; it is 41 consolidated editions with dates. A labour
dispute is always about the law *when it happened*, so "which text was in force
on 2021-09-01" is a product feature, not an archive nicety.

This script discovers every edition of act XII-2603 on the portal, downloads the
DOCX of each, parses it with the same parser the live corpus uses, and stores
**one record per article per version** rather than one copy of the code per
edition. Most articles never change, so the difference between 41 full editions
(~18 MB) and their distinct versions is roughly an order of magnitude.

    python build_history.py                           # fetch anything missing, rebuild
    python build_history.py --materialise             # rewrite data/articles.json from
                                                      # the edition in force today
    python build_history.py --materialise --on DATE   # stage a specific edition

Output:
    data/history.json          editions + per-article versions
    data/history_raw/          downloaded DOCX, cached so a rebuild is offline
"""

import hashlib
import json
import re
import sys
import time
import urllib.request
import zipfile

from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import history
import paragraphs
import parse_corpus
import refresh_corpus

ROOT = Path(__file__).parent
ACT_ID = refresh_corpus.ACT_ID
EDITIONS_PAGE = f"https://www.e-tar.lt/portal/lt/legalActEditions/{ACT_ID}"
RAW_DIR = ROOT / "data" / "history_raw"
HISTORY = ROOT / "data" / "history.json"
ARTICLES = ROOT / "data" / "articles.json"

EDITION_LINK = re.compile(
    rf'href="/portal/lt/legalAct/{ACT_ID}/([A-Za-z0-9]+)"[^>]*>Suvestinė nuo (\d{{4}}-\d{{2}}-\d{{2}})'
)

REQUEST_DELAY = 0.4  # seconds between downloads; this is a public service


def fetch_page():
    return refresh_corpus.fetch(EDITIONS_PAGE).decode("utf-8", "replace")


def discover(page=None):
    """Every edition the portal lists, newest first as published."""
    page = page if page is not None else fetch_page()
    editions = [
        {"valid_from": day, "token": token}
        for token, day in EDITION_LINK.findall(page)
    ]
    if not editions:
        sys.exit(
            "no editions found -- the portal layout changed. Check "
            f"{EDITIONS_PAGE} and EDITION_LINK in this file."
        )
    return editions


def cached_docx(edition):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{edition['valid_from']}-{edition['token']}.docx"
    if path.exists() and path.stat().st_size > 1000:
        return path.read_bytes()
    url = (
        f"https://www.e-tar.lt/rs/actualedition/{ACT_ID}/{edition['token']}"
        f"/format/MSO2010_DOCX/"
    )
    blob = refresh_corpus.fetch(url)
    if not blob.startswith(b"PK"):
        sys.exit(f"{edition['valid_from']}: e-TAR did not return a DOCX")
    path.write_bytes(blob)
    time.sleep(REQUEST_DELAY)
    return blob


def articles_for(edition):
    """Parse one edition into article records, using the production parser."""
    text = refresh_corpus.docx_text(cached_docx(edition))
    start, end = refresh_corpus.edition_window(text)
    lines = text.split("\n")

    region_start, region_end = parse_corpus.find_code_region(lines)
    saved = (parse_corpus.EDITION_FROM, parse_corpus.EDITION_TO)
    parse_corpus.EDITION_FROM, parse_corpus.EDITION_TO = start, end
    try:
        return parse_corpus.parse_articles(lines, region_start, region_end), start, end
    finally:
        parse_corpus.EDITION_FROM, parse_corpus.EDITION_TO = saved


def digest(record):
    payload = json.dumps(
        [record["title"], record["text"]], ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build(editions):
    """Download and diff every edition, then fold into per-article versions."""
    editions = sorted(editions, key=lambda e: e["valid_from"])
    parsed = []
    for edition in editions:
        records, start, end = articles_for(edition)
        parsed.append({
            "valid_from": start,
            "valid_to": end,
            "token": edition["token"],
            "count": len(records),
            "articles": records,
        })
        print(f"  {start} .. {end}  {len(records)} articles  ({edition['token']})")

    # valid_to comes from each document's own header, so no arithmetic on dates.
    windows = {e["valid_from"]: e["valid_to"] for e in parsed}

    versions = {}
    for edition in parsed:
        for record in edition["articles"]:
            entry = {
                "from": edition["valid_from"],
                "to": edition["valid_to"],
                "title": record["title"],
                "text": record["text"],
                "fingerprint": digest(record),
            }
            timeline = versions.setdefault(record["article"], [])
            if timeline and timeline[-1]["fingerprint"] == entry["fingerprint"]:
                # Unchanged: extend the version instead of storing it twice.
                timeline[-1]["to"] = entry["to"]
            else:
                timeline.append(entry)

    return {
        "act": "XII-2603",
        "source": "e-TAR",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "editions": [
            {"valid_from": e["valid_from"], "valid_to": windows[e["valid_from"]],
             "count": e["count"]}
            for e in parsed
        ],
        "articles": versions,
    }




def materialise(data, on=None):
    """Write data/articles.json from the edition in force, keeping the schema."""
    on = on or date.today().isoformat()
    edition = history.in_force(on, data)
    if edition is None:
        sys.exit(f"no edition is in force on {on}; refusing to build a corpus from nothing")

    records = []
    for identifier in sorted(
        data["articles"], key=lambda i: (int(i.split("-")[0]), i)
    ):
        version = history.article_as_of(identifier, on, data)
        if version is None:
            continue  # repealed or not yet enacted on this date
        records.append({
            "article": identifier,
            "citation": identifier.replace("-", "¹", 1) if "-" in identifier else identifier,
            "title": version["title"],
            "text": version["text"],
            "parts": paragraphs.split_parts(version["text"]),
            "source": parse_corpus.SOURCE,
            "act_number": parse_corpus.ACT_NUMBER,
            "edition_from": edition["valid_from"],
            "edition_to": edition["valid_to"],
        })

    ARTICLES.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {ARTICLES} from the edition in force on {on} "
          f"({edition['valid_from']} .. {edition['valid_to']}, {len(records)} articles)")


def main(argv):
    print(f"discovering editions: {EDITIONS_PAGE}")
    editions = discover()
    print(f"found {len(editions)} editions")

    data = build(editions)
    HISTORY.write_text(
        json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )
    size = HISTORY.stat().st_size / 1024
    versions = sum(len(v) for v in data["articles"].values())
    changed = sum(1 for v in data["articles"].values() if len(v) > 1)
    print(
        f"\nwrote {HISTORY.relative_to(ROOT)}: {size:.0f} KiB, "
        f"{len(data['articles'])} articles, {versions} versions "
        f"({changed} articles changed at least once)"
    )

    if "--materialise" in argv:
        on = None
        if "--on" in argv:
            on = argv[argv.index("--on") + 1]
        materialise(data, on)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
