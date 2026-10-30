"""Ingest Sodra's published explanations of benefits tied to employment.

Sodra (the social insurance fund) explains sickness, maternity/paternity,
unemployment and work-injury benefits in plain language. Those are the numbers a
worker asks about after the Labour Code says they are entitled to something.

The pages are server-rendered, unlike the sites that needed the browser bridge.
Navigation is stripped before chunking; benefit pages carry a large menu.

    python ingest_sodra.py            # crawl and report
    python ingest_sodra.py --write    # write data/sodra.json
"""

import html
import json
import re
import sys

from pathlib import Path

import refresh_corpus

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "sodra.json"
MAX_CHARS = 1500
MAX_PAGES = 30

SEEDS = (
    "https://sodra.lt/ismokos/darbo-ismokos/gauti-nedarbo-ismoka",
    "https://sodra.lt/ismokos/sveikatos-ir-neigalumo-ismokos",
    "https://sodra.lt/ismokos/gyventojams",
)


def plain(page):
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    for tag in ("header", "footer", "nav", "form"):
        text = re.sub(rf"<{tag}\b.*?</{tag}>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in html.unescape(text).splitlines()]
    return [line for line in lines if len(line) > 30]


def title_of(page):
    match = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(match.group(1))).split("–")[0].strip() if match else ""


def is_content(text):
    """Drop menu, cookie and footer text that survives tag stripping."""
    lowered = text.lower()
    if "„sodra“" in text[:150].lower():
        return False  # page title followed by the site chrome
    if "slapuk" in lowered or "rekvizitai kontaktai" in lowered:
        return False
    if text.count(" – ") > 5:  # menu items are joined with dashes
        return False
    return len(text) >= 120


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


def crawl():
    seen, pages = set(), []
    queue = list(SEEDS)
    while queue and len(pages) < MAX_PAGES:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            page = refresh_corpus.fetch(url).decode("utf-8", "replace")
        except Exception as error:
            print(f"  skip {url}: {type(error).__name__}")
            continue
        pages.append((url, page))
        for link in re.findall(r'href="((?:https://sodra\.lt)?/ismokos/[^"#?]+)"', page):
            candidate = link if link.startswith("http") else "https://sodra.lt" + link
            if candidate not in seen and candidate not in queue:
                queue.append(candidate)
    return pages


def records(pages=None):
    # Read the committed snapshot when there is one. A live crawl is the
    # discovery path, not the build path: a transient network failure there
    # silently deleted 248 Sodra chunks once, because the index is rebuilt from
    # whatever this function returns.
    if pages is None and OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    pages = pages if pages is not None else crawl()
    out = []
    for index, (url, page) in enumerate(pages, start=1):
        title = title_of(page) or f"Sodra {index}"
        for part, text in enumerate(chunks(plain(page)), start=1):
            if not is_content(text):
                continue
            out.append({
                "id": f"sodra-{index}-{part}",
                "source": "Sodra paaiškinimas",
                "act_id": url,
                "act_title": title,
                "authority": "Valstybinio socialinio draudimo fondo valdyba",
                "act_date": "",
                "url": url,
                "annex": "",
                "chapter": "",
                "ref": str(part),
                "valid_from": "2026-10-30",
                "valid_to": "9999-12-31",
                "citation": f"Sodra paaiškinimas: {title}, {part} fragmentas",
                "title": f"{title} — {text[:90]}",
                "text": text,
            })
    return out


def main(argv=None):
    pages = crawl()
    items = records(pages)
    print(f"{len(pages)} pages, {len(items)} chunks")
    for url, _ in pages[:5]:
        print("  -", url)
    if "--write" in (argv or sys.argv[1:]):
        OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
