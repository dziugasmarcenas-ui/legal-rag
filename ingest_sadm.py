"""Ingest the Social Security and Labour Ministry's published answers.

SADM's FAQ is the ministry's own reading of the labour and social-security rules
it administers, and it is server-rendered HTML (unlike VDI's JS listing), so it
can be parsed directly.

    python ingest_sadm.py            # parse and report
    python ingest_sadm.py --write    # write data/sadm.json
"""

import html
import json
import re
import sys

from pathlib import Path

import refresh_corpus

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "sadm.json"
BASE = "https://socmin.lrv.lt/lt/duk/"

HEADER = re.compile(r'<a\s[^>]*id="([^"]+)-header"[^>]*>(.*?)</a>', re.S)
MAX_CHARS = 1500


def plain(fragment):
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", fragment, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_page(page):
    matches = list(HEADER.finditer(page))
    out = []
    for index, match in enumerate(matches):
        question = plain(match.group(2))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(page)
        answer = plain(page[start:end])
        if not question.endswith("?") or len(answer) < 80:
            continue
        if question in {item["question"] for item in out}:
            continue
        out.append({"question": question, "answer": answer})
    return out


def split_answer(text, limit=MAX_CHARS):
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if current and len(current) + len(sentence) > limit:
            parts.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current:
        parts.append(current.strip())
    return parts


def fetch_items():
    page = refresh_corpus.fetch(BASE).decode("utf-8", "replace")
    return parse_page(page)


def records(items=None):
    items = items if items is not None else (
        json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else fetch_items()
    )
    out = []
    for index, item in enumerate(items, start=1):
        body = item["question"] + "\n" + item["answer"]
        for part, text in enumerate(split_answer(body), start=1):
            out.append({
                "id": f"sadm-faq-{index}-{part}",
                "source": "SADM paaiškinimas",
                "act_id": "sadm-faq",
                "act_title": "Socialinės apsaugos ir darbo ministerijos atsakymai į klausimus",
                "authority": "Socialinės apsaugos ir darbo ministerija",
                "act_date": "",
                "url": BASE,
                "annex": "",
                "chapter": "",
                "ref": str(index),
                "valid_from": "2026-10-30",
                "valid_to": "9999-12-31",
                "citation": f"SADM paaiškinimas Nr. {index}",
                "title": item["question"][:110],
                "text": text,
            })
    return out


def main(argv=None):
    items = fetch_items()
    print(f"{len(items)} answered questions")
    for item in items[:5]:
        print(" -", item["question"][:90])
    if "--write" in (argv or sys.argv[1:]):
        OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
