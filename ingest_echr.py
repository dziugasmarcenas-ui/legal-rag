"""Ingest ECHR judgments concerning Lithuania, filtered to labour questions.

The Convention is part of the law Lithuanian courts apply, and the Strasbourg
cases against Lithuania are where "freedom of association", "private life at
work" and "fair trial in a labour dispute" actually get defined. HUDOC exposes a
JSON query API and a document-body endpoint, so this needs no browser.

Filtering matters: 10,000+ documents mention Lithuania. The query narrows to
employment-related terms before anything is fetched.

    python ingest_echr.py            # query and report
    python ingest_echr.py --write    # write data/echr.json
"""

import html
import json
import re
import sys
import urllib.parse
import urllib.request

from pathlib import Path

import refresh_corpus

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "echr.json"
API = "https://hudoc.echr.coe.int/app/query/results"
BODY = "https://hudoc.echr.coe.int/app/conversion/docx/html/body?library=ECHR&id={}"
CASE = "https://hudoc.echr.coe.int/eng?i={}"

QUERY = (
    'contentsitename:ECHR AND (Lithuania) AND '
    '(labour OR employment OR "freedom of association" OR "trade union" OR '
    '"right to respect for private life")'
)
LIMIT = 40
MAX_CHARS = 1600


def fetch(url, accept="application/json"):
    request = urllib.request.Request(
        url, headers={"User-Agent": refresh_corpus.USER_AGENT, "Accept": accept}
    )
    with urllib.request.urlopen(
        request, timeout=60, context=refresh_corpus.SSL_CONTEXT
    ) as response:
        return response.read().decode("utf-8", "replace")


def search():
    params = urllib.parse.urlencode({
        "query": QUERY,
        "select": "itemid,docname,appno,judgmentdate,kpdate",
        "sort": "",
        "start": 0,
        "length": LIMIT,
    })
    payload = json.loads(fetch(f"{API}?{params}"))
    return [row["columns"] for row in payload.get("results", [])]


def lithuanian_name(docname):
    """"CASE OF JANKAUSKAS v. LITHUANIA" -> "Jankauskas p. Lietuvą"."""
    text = re.sub(r"^(CASE OF|JUDGMENT)\s+", "", docname, flags=re.I)
    applicant = re.split(r"\s+v\.\s+", text, flags=re.I)[0]
    applicant = re.sub(r"\s*-\s*.*$", "", applicant).strip()
    # Lithuanian citation style names the first applicant: "Hoppen p. Lietuvą",
    # not the full company name of every applicant.
    applicant = re.split(r"\s+(?:and|AND)\s+|\s+ir\s+", applicant)[0].strip()
    return f"{applicant.title()} p. Lietuvą"


def plain(page):
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in html.unescape(text).splitlines()]
    return [line for line in lines if line]


def chunks(lines):
    out, current = [], ""
    for line in lines:
        if current and len(current) + len(line) > MAX_CHARS:
            out.append(current)
            current = line
        else:
            current = (current + " " + line).strip()
    if current:
        out.append(current)
    return out


def records():
    out = []
    seen = set()
    for case in search():
        itemid = case.get("itemid")
        docname = case.get("docname", "")
        if not itemid or "LITHUANIA" not in docname.upper():
            continue
        try:
            body = fetch(BODY.format(itemid), accept="text/html")
        except Exception as error:
            print(f"  {docname}: skipped ({type(error).__name__})")
            continue
        name = lithuanian_name(docname)
        # HUDOC returns the same judgment once per language and once per
        # document type; a connector must not present duplicates as case law.
        # The application number is the same across language versions and
        # document types; the name is not.
        key = case.get("appno") or re.sub(r"[^a-z]", "", name.lower())
        if key in seen:
            continue
        seen.add(key)
        pieces = chunks(plain(body))
        for index, text in enumerate(pieces, start=1):
            if len(text) < 200:
                continue
            out.append({
                "id": f"echr-{itemid}-{index}",
                "source": "EŽTT sprendimas",
                "act_id": itemid,
                "act_title": name,
                "authority": "Europos Žmogaus Teisių Teismas",
                "act_date": case.get("judgmentdate", ""),
                "url": CASE.format(itemid),
                "annex": "",
                "chapter": "",
                "ref": str(index),
                "valid_from": case.get("judgmentdate") or "1959-01-21",
                "valid_to": "9999-12-31",
                "citation": (
                    f"EŽTT, {name} (Nr. {case['appno']}), {index} fragmentas"
                    if case.get("appno")
                    else f"EŽTT, {name}, {index} fragmentas"
                ),
                "title": f"{name} — {text[:90]}",
                "text": text,
            })
        print(f"  {name}: {len(pieces)} fragments")
    return out


def main(argv=None):
    items = records()
    print(f"{len(items)} fragments from {len({i['act_id'] for i in items})} judgments")
    if "--write" in (argv or sys.argv[1:]):
        OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
