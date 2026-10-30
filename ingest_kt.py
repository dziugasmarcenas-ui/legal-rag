"""Ingest Constitutional Court rulings that interpret labour and social-security law.

The case graph currently holds only ECHR judgments, because LITEKO (the national
court database) is captcha-protected. The Constitutional Court is different: its
rulings are registered in e-seimas, fetched as DOCX, and they decide what the
labour and social-insurance statutes mean. A ruling that a provision is
unconstitutional changes the law the Code points at.

Records are labelled "KT nutarimas" and carry the case number and decision date.
Only the passages that discuss labour or social security are kept: a ruling is
mostly procedural text, and dumping it whole would bury the reasoning.

    python ingest_kt.py            # parse data/kt_raw, report
    python ingest_kt.py --write    # write data/kt.json
"""

import json
import re
import sys

from pathlib import Path

import refresh_corpus

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "kt_raw"
OUT = ROOT / "data" / "kt.json"
MAX_CHARS = 1600

# The registered PDF/DOCX sometimes renders "Byla" as "By1a"; the case number
# also appears in the body ("konstitucinės justicijos bylą Nr. 44/2009").
CASE = re.compile(r"By[1l]a\s+Nr\.?\s*([0-9][0-9/\-–]*[0-9])", re.I)
CASE_BODY = re.compile(r"bylą\s+Nr\.?\s*([0-9][0-9/\-–]*[0-9])", re.I)
# The decision date is the date that precedes the place of sitting; earlier
# dates in the heading belong to the statutes under review.
DATE = re.compile(
    r"(\d{4})\s*m\.\s*([a-ząčęėįšųūž]+)\s*(\d{1,2})\s*d\.\s*"
    r"(?:Nr\.[^\n]{0,40})?\s*Vilnius"
)
TITLE = re.compile(r"N\s*U\s*T\s*A\s*R\s*I\s*M\s*A\s*S(.*?)\d{4}\s*m\.", re.S)

LABOUR = (
    "darbo kodeks", "darbuotoj", "darbo užmokesč", "atostog", "atleid",
    "socialinio draudimo", "profesin", "nelaiming", "ligos ir motinystės",
    "išeitin", "kolektyvin", "profesinių sąjung", "darbo ginč",
)

MONTHS = {
    "sausio": "01", "vasario": "02", "kovo": "03", "balandžio": "04",
    "gegužės": "05", "birželio": "06", "liepos": "07", "rugpjūčio": "08",
    "rugsėjo": "09", "spalio": "10", "lapkričio": "11", "gruodžio": "12",
}


def clean(text):
    text = text.replace("\u00ad", "").replace("\u200b", "").replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text)


def title_of(text):
    match = TITLE.search(text[:4000])
    if not match:
        return ""
    raw = re.sub(r"\s+", " ", match.group(1)).strip(" /")
    return raw[:220]


def date_of(text):
    match = DATE.search(text[:4000])
    if not match:
        return ""
    year, month, day = match.group(1), MONTHS.get(match.group(2), ""), match.group(3)
    return f"{year}-{month}-{int(day):02d}" if month else ""


def case_of(text):
    match = CASE.search(text[:600]) or CASE_BODY.search(text[:8000])
    return match.group(1).strip() if match else ""


def chunks(lines):
    """Paragraph-wise chunks; a ruling's reasoning is one long argument."""
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


def is_labour(text):
    lowered = text.lower()
    return sum(1 for word in LABOUR if word in lowered) >= 2


def records():
    out = []
    for path in sorted(RAW.glob("*.docx")):
        text = clean(refresh_corpus.docx_text(path.read_bytes()))
        case = case_of(text)
        decided = date_of(text)
        heading = title_of(text)
        if not case or not decided:
            print(f"  {path.name}: skipped (case={case!r}, date={decided!r})")
            continue

        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        lines = [line for line in lines if len(line) > 60]
        kept = [chunk for chunk in chunks(lines) if is_labour(chunk)]

        for index, body in enumerate(kept, start=1):
            out.append({
                "id": f"kt-{case}-{index}",
                "source": "KT nutarimas",
                "act_id": f"kt-{case}",
                "act_title": heading or f"KT nutarimas, byla Nr. {case}",
                "authority": "Lietuvos Respublikos Konstitucinis Teismas",
                "act_date": decided,
                "url": f"https://e-seimas.lrs.lt/portal/legalAct/lt/TAD/{path.stem[4:]}",
                "annex": "",
                "chapter": "",
                "ref": str(index),
                "valid_from": decided,
                "valid_to": "9999-12-31",
                "citation": f"KT nutarimas, byla Nr. {case}, {index} fragmentas",
                "title": f"KT nutarimas, byla Nr. {case} — {body[:90]}",
                "text": body,
            })
        print(f"  byla Nr. {case} ({decided}): {len(kept)} labour fragments")
    return out


def main(argv=None):
    items = records()
    print(f"{len(items)} fragments from {len({i['act_id'] for i in items})} rulings")
    if "--write" in (argv or sys.argv[1:]):
        OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
