"""Ingest Seimas sitting transcripts, filtered to labour and social affairs.

The Seimas site (lrs.lt) is behind a Cloudflare challenge that answers every
non-browser client with 403, including its `getFile3` document endpoint. The
practical route is a real browser session: fetch the PDF in the page, POST it to
a loopback receiver, and parse it here. `data/seimas_raw/` holds those exports.

Plenary transcripts are broad political record. Dumping 438 pages into a legal
retriever would bury the law, so only passages that mention labour or social
security terms are kept, with their surrounding lines.

    python ingest_seimas.py            # parse what is in data/seimas_raw
    python ingest_seimas.py --write    # write data/seimas.json
"""

import json
import re
import sys

from pathlib import Path

import pymupdf

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "seimas_raw"
OUT = ROOT / "data" / "seimas.json"
MAX_CHARS = 1600

KEYWORDS = (
    "darbo kodeks", "darbo užmokes", "atostog", "atleid", "darbuotoj",
    "socialin", "pensij", "nedarbing", "vaiko priežiūr", "profesin",
    "užimtum", "komandiruot", "viršvaland",
)

TITLE = re.compile(r"Stenogramos\s*\n?\s*(\d{1,3})", re.I)
DATE = re.compile(r"(\d{4}) m\. ([a-ząčęėįšųūž]+) (\d{1,2}) d\.")


def page_text(path):
    """Extract text and repair the layer that looked broken.

    pypdf reported this as syllable-split text; PyMuPDF shows the real cause:
    soft hyphens (U+00AD) inside words. Stripping them and joining hyphenated
    line breaks turns "pa\xadtai\xadsa" into "pataisa".
    """
    document = pymupdf.open(path)
    raw = "\n".join(page.get_text() for page in document)
    raw = raw.replace("\xad", "").replace("\u200b", "")
    raw = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    return raw


def is_index_line(text):
    """Table-of-contents lines are dots and page numbers, not debate."""
    dots = text.count(".")
    return dots > 20 or dots > len(text) / 5


def looks_clean(text):
    """Reject the PDF's broken text layer.

    This PDF splits words syllable by syllable ("La bai ačiū už klau si mą"),
    which is unusable for retrieval. A high share of one- and two-letter tokens
    is the signature.
    """
    tokens = text.split()
    if len(tokens) < 8:
        return True
    # Two-letter syllables are the signature of the split text layer; ordinary
    # Lithuanian prose has few tokens that short.
    short = sum(1 for token in tokens if len(token) <= 2)
    return short / len(tokens) < 0.25


def relevant(lines):
    """Keep passages that mention labour or social security, plus neighbours.

    A single matching line is rarely intelligible; one line either side usually
    carries the subject and the speaker.
    """
    keep = set()
    for index, line in enumerate(lines):
        if any(keyword in line.lower() for keyword in KEYWORDS):
            for neighbour in (index - 2, index - 1, index, index + 1, index + 2):
                if 0 <= neighbour < len(lines):
                    keep.add(neighbour)

    blocks, current = [], []
    for index in sorted(keep):
        if current and index != current[-1] + 1:
            blocks.append(current)
            current = []
        current.append(index)
    if current:
        blocks.append(current)

    out = []
    for block in blocks:
        text = re.sub(r"\s+", " ", " ".join(lines[i] for i in block)).strip()
        if is_index_line(text) or not looks_clean(text):
            continue
        out.append(text)
    return out


def chunks(blocks):
    out, current = [], ""
    for block in blocks:
        if len(block) < 60:
            continue
        if current and len(current) + len(block) > MAX_CHARS:
            out.append(current)
            current = block
        else:
            current = (current + " " + block).strip()
    if current:
        out.append(current)
    return out


def records():
    out = []
    for index, path in enumerate(sorted(RAW.glob("*.pdf")), start=1):
        text = page_text(path)
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        lines = [line for line in lines if line]

        title_match = TITLE.search(text[:3000])
        number = title_match.group(1) if title_match else str(index)
        date_match = DATE.search(text[:4000])
        started = (
            f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            if date_match else ""
        )

        for part, chunk in enumerate(chunks(relevant(lines)), start=1):
            out.append({
                "id": f"seimas-{number}-{part}",
                "source": "Seimo stenogramos",
                "act_id": f"seimas-{number}",
                "act_title": f"Seimo posėdžių stenogramų rinkinys Nr. {number}",
                "authority": "Lietuvos Respublikos Seimas",
                "act_date": started,
                "url": "https://www.lrs.lt/sip/portal.show?p_r=39771&p_k=1",
                "annex": "",
                "chapter": "",
                "ref": str(part),
                "valid_from": started or "2020-09-24",
                "valid_to": "9999-12-31",
                "citation": f"Seimo stenogramos Nr. {number}, {part} fragmentas",
                "title": f"Seimo stenogramos Nr. {number} — {chunk[:90]}",
                "text": chunk,
            })
        print(f"{path.name}: {len(chunks(relevant(lines)))} labour-related fragments")
    return out


def main(argv=None):
    items = records()
    print(f"{len(items)} fragments")
    if "--write" in (argv or sys.argv[1:]):
        OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
