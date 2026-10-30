"""Ingest Seimas draft acts (TAP) exported from e-seimas.

The transcript PDFs are unusable (their text layer splits words per syllable),
but draft acts are served as DOCX from e-seimas and extract cleanly. Drafts are
what the parliament is considering: the bill that would change article 221, not
the article as it stands.

They are not law. Records are labelled "Seimo projektas" and the prompt is told
to say a draft is not adopted; the gate never lets a draft decide an answer.

    python ingest_seimas_drafts.py            # parse data/seimas_raw/tap-*.docx
    python ingest_seimas_drafts.py --write    # write data/seimas_drafts.json
"""

import json
import re
import sys

from pathlib import Path

import refresh_corpus

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "seimas_raw"
OUT = ROOT / "data" / "seimas_drafts.json"
MAX_CHARS = 1500

ARTICLE = re.compile(r"^(\d{1,3}) straipsnis\.\s*(.*)$")
REGISTRATION = re.compile(r"Nr\.\s*([A-Za-z0-9()\-]*\d[A-Za-z0-9()\-]*)")
LABOUR = ("darbo", "socialin", "darbuotoj", "užimtum", "atostog", "užmokesč",
          "pensij", "nedarbing", "komandiruot")


def title_of(text):
    lines = [line for line in text.splitlines() if line.strip()]
    head = []
    for line in lines[:6]:
        if line.startswith(("Projektas", "LIETUVOS RESPUBLIKOS")):
            continue
        head.append(line)
    return " ".join(head)[:160].strip()


def registration_of(text):
    match = REGISTRATION.search(text[:400])
    return match.group(1) if match else ""


def is_labour(text):
    head = text[:1200].lower()
    return any(keyword in head for keyword in LABOUR)


def article_chunks(text):
    """Split a draft by its articles; fall back to paragraph chunks."""
    lines = text.splitlines()
    starts = [
        (index, match.group(1), match.group(2))
        for index, line in enumerate(lines)
        if (match := ARTICLE.match(line.strip()))
    ]
    if not starts:
        out, current = [], ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if current and len(current) + len(line) > MAX_CHARS:
                out.append(("", current))
                current = line
            else:
                current = (current + " " + line).strip()
        if current:
            out.append(("", current))
        return out

    out = []
    for position, (index, number, heading) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        body = " ".join(line.strip() for line in lines[index:end] if line.strip())
        out.append((number, body))
    return out


def records():
    out = []
    for path in sorted(RAW.glob("tap-*.docx")):
        text = refresh_corpus.docx_text(path.read_bytes())
        if not is_labour(text):
            continue
        title = title_of(text)
        registration = registration_of(text)
        number = f"Nr. {registration}" if registration else "be numerio"

        for index, (article, body) in enumerate(article_chunks(text), start=1):
            reference = f"{article} str." if article else f"{index} fragmentas"
            out.append({
                # The full stem: the last twelve characters of two different
                # TAP files can coincide (both ended "...e3dbc2261ee42a").
                "id": f"tap-{path.stem}-{index}",
                "source": "Seimo projektas",
                "act_id": path.stem,
                "act_title": title,
                "authority": "Lietuvos Respublikos Seimas",
                "act_date": "",
                "url": "https://e-seimas.lrs.lt/portal/legalActProjectSearch/lt",
                "annex": "",
                "chapter": "",
                "ref": article or str(index),
                "valid_from": "2026-10-30",
                "valid_to": "9999-12-31",
                "citation": f"Seimo projektas {number}, {reference}",
                "title": f"{title} — {reference}",
                "text": body[:MAX_CHARS] if body else "",
            })
    return [record for record in out if len(record["text"]) > 40]


def main(argv=None):
    items = records()
    print(f"{len(items)} chunks from {len({i['act_id'] for i in items})} drafts")
    for item in items[:5]:
        print(f"  {item['citation']} | {item['title'][:80]}")
    if "--write" in (argv or sys.argv[1:]):
        OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
