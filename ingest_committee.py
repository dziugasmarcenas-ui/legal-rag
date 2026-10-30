"""Ingest Seimas committee conclusions on labour bills.

Committee *transcripts* are not published on e-seimas or lrs.lt — the only
"Stenograma" document type returns plenary sittings. What is published is the
committee's reasoned conclusion on a bill ("KOMITETO IŠVADA dėl Darbo kodekso
... projekto"), which is the committee's stated position and often the only
place the reasoning behind an amendment is written down.

They are not law and they are not verbatim debate. Records are labelled
"Seimo komiteto išvada" and the prompt treats them like a draft: cited, and
described as a committee opinion rather than an adopted rule.

    python ingest_committee.py            # parse data/committee_raw
    python ingest_committee.py --write    # write data/committee.json
"""

import json
import re
import sys

from pathlib import Path

import refresh_corpus

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "committee_raw"
OUT = ROOT / "data" / "committee.json"
MAX_CHARS = 1600

MONTHS = {
    "sausio": "01", "vasario": "02", "kovo": "03", "balandžio": "04",
    "gegužės": "05", "birželio": "06", "liepos": "07", "rugpjūčio": "08",
    "rugsėjo": "09", "spalio": "10", "lapkričio": "11", "gruodžio": "12",
}
DATE = re.compile(r"(\d{4})\s*m\.\s*([a-ząčęėįšųūž]+)\s*(\d{1,2})\s*d\.")
ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
# "KOMITETO IŠVADA" also appears as "PAPILDOMO KOMITETO I Š V A D O S".
CONCLUSION = re.compile(r"I\s*Š\s*V\s*A\s*D", re.I)


def clean(text):
    text = text.replace("\u00ad", "").replace("\u200b", "").replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text)


def title_of(text):
    """Committee name plus the bill the conclusion is about."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    committee = next(
        (line for line in lines[:4] if re.search(r"komitetas", line, re.I)), ""
    )
    start = next(
        (i for i, line in enumerate(lines[:8]) if CONCLUSION.search(line)), 0
    )
    subject = []
    for line in lines[start + 1:start + 6]:
        if re.match(r"^(Nr\.|\d{4}-\d{2}-\d{2}|Vilnius)", line):
            break
        subject.append(line)
    committee = re.sub(r"^LIETUVOS RESPUBLIKOS SEIMO\s*", "", committee, flags=re.I)
    text_out = " ".join(subject).strip()
    text_out = re.sub(r"^(DĖL|Dėl)\s+", "", text_out)
    title = f"{committee.strip()}: {text_out}" if committee else text_out
    return title[:220]


def date_of(text):
    iso = ISO.search(text[:1200])
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    match = DATE.search(text[:1500])
    if not match:
        return ""
    month = MONTHS.get(match.group(2), "")
    return f"{match.group(1)}-{month}-{int(match.group(3)):02d}" if month else ""


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
    for index, path in enumerate(sorted(RAW.glob("*.docx")), start=1):
        text = clean(refresh_corpus.docx_text(path.read_bytes()))
        if not CONCLUSION.search(text[:2500]):
            print(f"  {path.name}: skipped (not a committee conclusion)")
            continue
        title = title_of(text)
        decided = date_of(text)
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        lines = [line for line in lines if len(line) > 60]

        for part, body in enumerate(chunks(lines), start=1):
            out.append({
                # The full stem: three exports shared their last twelve
                # characters, which collapsed 103 fragments under one id.
                "id": f"{path.stem}-{part}",
                "source": "Seimo komiteto išvada",
                "act_id": path.stem,
                "act_title": title or "Seimo komiteto išvada",
                "authority": "Lietuvos Respublikos Seimo komitetas",
                "act_date": decided,
                "url": "https://e-seimas.lrs.lt/portal/documentSearch/lt",
                "annex": "",
                "chapter": "",
                "ref": str(part),
                "valid_from": decided or "2026-10-30",
                "valid_to": "9999-12-31",
                "citation": f"Seimo komiteto išvada Nr. {index}, {part} fragmentas",
                "title": f"Seimo komiteto išvada — {(title or 'dėl projekto')[:110]}",
                "text": body,
            })
        print(f"  {path.name}: {len(chunks(lines))} fragments | {title[:80]}")
    return out


def main(argv=None):
    items = records()
    print(f"{len(items)} fragments from {len({i['act_id'] for i in items})} conclusions")
    if "--write" in (argv or sys.argv[1:]):
        OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
