"""Ingest VDI's published answers to the questions employers actually ask.

The inspectorate's FAQ is not a legal act, but it is the institution's stated
position on how it applies the law, and it answers the questions that never make
it into a statute ("do I need a safety service if the company is one director and
an accountant?"). That is Phase 4's "institution explanations".

The list is server-rendered inside accordion panels, so this parses the page
rather than chasing an API that does not exist.

    python ingest_explanations.py          # print what would be ingested
    python ingest_explanations.py --write  # append to data/explanations.json
"""

import html
import re
import sys
import time

from pathlib import Path

import refresh_corpus

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "explanations.json"
BASE = "https://vdi.lrv.lt/lt/dazniausiai-uzduodami-klausimai/"
HEADER = re.compile(
    r'<a\s[^>]*id="(accordion-[\w-]+)-header"[^>]*>(.*?)</a>', re.S
)
PAGES = 8  # the listing paginates; stop early when a page adds nothing new
REQUEST_DELAY = 0.4


def plain(fragment):
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", fragment, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_page(page):
    """Question from the accordion header, answer from what follows it."""
    matches = list(HEADER.finditer(page))
    out = []
    for index, match in enumerate(matches):
        question = plain(match.group(2))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(page)
        answer = plain(page[start:end])
        if not question.endswith("?") or len(answer) < 80:
            continue
        out.append({"question": question, "answer": answer})
    return out


def fetch_all():
    seen, items = set(), []
    for number in range(1, PAGES + 1):
        url = BASE if number == 1 else f"{BASE}?page={number}"
        try:
            page = refresh_corpus.fetch(url).decode("utf-8", "replace")
        except Exception:
            break
        fresh = [q for q in parse_page(page) if q["question"] not in seen]
        if not fresh:
            break
        for item in fresh:
            seen.add(item["question"])
            items.append(item)
        time.sleep(REQUEST_DELAY)
    return items


def split_answer(text, limit=1500):
    """Long FAQ answers become several chunks that still cite the same Q&A."""
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


def records(items=None):
    """The same record shape the act chunks use, so retrieval needs no branch."""
    items = items if items is not None else json_load()
    out = []
    for index, item in enumerate(items, start=1):
        body = item["question"] + "\n" + item["answer"]
        for part, text in enumerate(split_answer(body), start=1):
            out.append({
            "id": f"vdi-faq-{index}-{part}",
            "source": "VDI paaiškinimas",
            "act_id": "vdi-faq",
            "act_title": "Valstybinės darbo inspekcijos atsakymai į dažniausius klausimus",
            "authority": "Valstybinė darbo inspekcija",
            "act_date": "",
            "url": BASE,
            "annex": "",
            "chapter": "",
            "ref": str(index),
            "valid_from": "2026-10-30",
            "valid_to": "9999-12-31",
            "citation": f"VDI paaiškinimas Nr. {index}",
            "title": item["question"][:110],
            "text": text,
        })
    return out


def json_load():
    import json

    if not OUT.exists():
        return []
    return json.loads(OUT.read_text(encoding="utf-8"))


def main(argv=None):
    items = fetch_all()
    print(f"{len(items)} answered questions")
    for item in items[:5]:
        print(" -", item["question"][:90])
    if "--write" in (argv or sys.argv[1:]):
        import json

        OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
