"""Ingest the EU labour directives Lithuania implements.

The Code's rules on working time, posted workers, collective redundancies and
equal treatment come from these directives. A connector that cannot show the
directive behind an article is answering half the question.

EUR-Lex serves the Lithuanian text from the Cellar resource endpoint, which is
the one that returns a document rather than a JavaScript shell:

    https://publications.europa.eu/resource/celex/{celex}

    python ingest_eu.py            # parse and report
    python ingest_eu.py --write    # write data/eu.json
"""

import html
import json
import re
import sys

from pathlib import Path

import refresh_corpus

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "eu.json"
BASE = "https://publications.europa.eu/resource/celex/{}"

DIRECTIVES = [
    ("32003L0088", "Direktyva 2003/88/EB", "Darbo laiko organizavimo tam tikri aspektai", "2003-11-04"),
    ("32019L1158", "Direktyva 2019/1158/ES", "Darbo ir šeimos gyvenimo pusiausvyra", "2019-06-20"),
    ("31996L0071", "Direktyva 96/71/EB", "Darbuotojų komandiravimas teikiant paslaugas", "1996-12-16"),
    ("31998L0059", "Direktyva 98/59/EB", "Kolektyvinio atleidimo procedūros", "1998-07-20"),
    ("32000L0078", "Direktyva 2000/78/EB", "Vienodas požiūris užimtumo ir profesinėje srityje", "2000-11-27"),
]

ARTICLE = re.compile(r"^(\d{1,3})\s*straipsnis$")


def plain(fragment):
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", fragment, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    return [re.sub(r"\s+", " ", line).strip() for line in html.unescape(text).splitlines()]


def parse(page, short):
    lines = [line for line in plain(page) if line]
    chunks, current = [], None

    for line in lines:
        match = ARTICLE.match(line)
        if match:
            if current:
                chunks.append(current)
            current = {"ref": match.group(1), "parts": []}
            continue
        if current is not None:
            current["parts"].append(line)

    if current:
        chunks.append(current)

    records = []
    for chunk in chunks:
        text = " ".join(chunk["parts"]).strip()
        if len(text) < 40:
            continue
        records.append({
            "ref": chunk["ref"],
            "citation": f"{short}, {chunk['ref']} str.",
            "title": f"{short} — {text[:90]}",
            "text": f"{chunk['ref']} straipsnis. {text}",
        })
    return records


def fetch(celex):
    import urllib.request

    request = urllib.request.Request(
        BASE.format(celex),
        headers={
            "User-Agent": refresh_corpus.USER_AGENT,
            # Cellar returns the document only when HTML is asked for; without
            # this it answers with a shell page and no articles.
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "lt",
        },
    )
    with urllib.request.urlopen(
        request, timeout=60, context=refresh_corpus.SSL_CONTEXT
    ) as response:
        return response.read().decode("utf-8", "replace")


def records():
    out = []
    for celex, short, title, date in DIRECTIVES:
        try:
            page = fetch(celex)
        except Exception as error:
            print(f"{short}: SKIPPED ({type(error).__name__})")
            continue
        articles = parse(page, short)
        print(f"{short}: {len(articles)} articles")
        seen_refs = {}
        for article in articles:
            # EUR-Lex repeats some article headings (contents block, annexes);
            # the second copy must not overwrite the first row.
            seen_refs[article["ref"]] = seen_refs.get(article["ref"], 0) + 1
            suffix = "" if seen_refs[article["ref"]] == 1 else f"-{seen_refs[article['ref']]}"
            out.append({
                "id": f"{celex}-{article['ref']}{suffix}",
                "source": short,
                "act_id": celex,
                "act_title": title,
                "authority": "Europos Sąjunga",
                "act_date": date,
                "url": f"https://eur-lex.europa.eu/legal-content/LT/TXT/?uri=CELEX:{celex}",
                "annex": "",
                "chapter": "",
                "ref": article["ref"],
                "valid_from": date,
                "valid_to": "9999-12-31",
                "citation": article["citation"],
                "title": article["title"],
                "text": article["text"],
            })
    return out


def main(argv=None):
    items = records()
    print(f"{len(items)} chunks")
    if "--write" in (argv or sys.argv[1:]):
        OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
