"""Parse the consolidated Lithuanian Labour Code into article-level records.

Input:  data/darbo_kodeksas_raw.txt  (text extracted from e-TAR, act XII-2603)
Output: data/articles.json           (one record per article)

Chunking decision: one record per article. Statute text is already divided by
its authors into self-contained, individually-citable units, so the document's
own structure is the chunking strategy. This also makes the citation
structural rather than generated -- the article number comes from a parsed
header, never from a language model.
"""

import re
import json

from pathlib import Path

SOURCE = "Lietuvos Respublikos darbo kodeksas"
ACT_NUMBER = "XII-2603"
EDITION_FROM = "2026-06-07"
EDITION_TO = "2026-10-31"
DATA = Path(__file__).parent / "data" / "darbo_kodeksas_raw.txt"
OUT = Path(__file__).parent / "data" / "articles.json"

# An article header looks like: "57 straipsnis. Darbo sutarties nutraukimas..."
# Group 1 is the number, group 2 is the title.
HEADER = re.compile(r"^(\d+) straipsnis\. (.+)$")

# Superscript articles. e-TAR renders article 72-1 as "721 straipsnis." because
# extracting text flattens the superscript. Left alone this invents a
# nonexistent article 721. The identifier is ASCII so it is easy to type in the
# golden set; the citation is how the Code itself writes it.
#   raw form -> (identifier, citation)
SUPERSCRIPT = {"721": ("72-1", "72¹")}

# Legislative bookkeeping interleaved inside article bodies. This is an exact
# list, NOT a pattern: real legal text also ends in ":" (for example
# "Darbo sutartis pasibaigia:" introduces the grounds for termination), so any
# rule based on the colon would delete substantive provisions.
ANNOTATIONS = {
    "Straipsnio pakeitimai:",
    "Straipsnio dalies pakeitimai:",
    "Straipsnio punkto pakeitimai:",
    "Straipsnio dalies numeracijos pakeitimas:",
    "Straipsnio punkto numeracijos pakeitimas:",
    "Straipsnio dalies naikinimas:",
    "Straipsnio punkto naikinimas:",
    "Papildyta straipsnio dalimi:",
    "Papildyta straipsnio punktu:",
    "Papildyta punktu:",
    "Pakeistas straipsnio pavadinimas:",
    "Skirsnio naikinimas:",
    "Priedo pakeitimai:",
}

# "Nr. XIII-2944, 2020-05-21, paskelbta TAR 2020-06-03, i. k. 2020-12135"
CITATION = re.compile(r"^Nr\. [IVX]+-\d+, \d{4}-\d{2}-\d{2}")


def load_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
        return text.split("\n")


def find_code_region(lines):
    start = None
    end = None

    for i, line in enumerate(lines):
        if line.strip() == "LIETUVOS RESPUBLIKOS DARBO KODEKSAS":
            start = i + 1

        if line.strip() == "Pakeitimai:":
            end = i
            break

    if start is None or end is None:
        raise ValueError(f"code region markers not found (start={start}, end={end})")

    return start, end


def is_structural(line):
    """True for part/chapter/section headers such as "II DALIS" and their
    all-caps titles. Statute body text always contains lowercase letters."""
    return not any(character.islower() for character in line)


def is_noise(line):
    """True for anything that is not the substance of the article."""
    if line in ANNOTATIONS:
        return True
    if CITATION.match(line):
        return True
    if is_structural(line):
        return True
    return False


def resolve_article_id(raw):
    """Return (identifier, citation) for a raw header number."""
    if raw in SUPERSCRIPT:
        return SUPERSCRIPT[raw]
    return raw, raw


def parse_articles(lines, start, end):
    """Scan the code region and build one record per article.

    Linear scan with an accumulator: walk the lines in order holding the
    article currently being filled in. A header line closes the previous
    article and opens a new one; every other line is either noise (dropped)
    or body text (appended).
    """
    articles = []
    current = None
    body = []
    previous_number = 0

    for line in lines[start:end]:
        line = line.strip()
        if not line:
            continue

        match = HEADER.match(line)
        if match:
            if current is not None:
                current["text"] = "\n".join(body)
                articles.append(current)

            raw = match.group(1)
            identifier, citation = resolve_article_id(raw)

            # Articles appear in ascending order. A number that jumps backwards
            # or wildly forwards is an unrecognised superscript, not a real
            # article -- fail loudly rather than inventing one.
            base = int(identifier.split("-")[0])
            if base < previous_number or base > previous_number + 5:
                raise ValueError(
                    f"article {raw!r} breaks the sequence "
                    f"(previous was {previous_number}). If this is a superscript "
                    f"article, add it to SUPERSCRIPT."
                )
            previous_number = base

            current = {
                "article": identifier,
                "citation": citation,
                "title": match.group(2).strip(),
                "text": "",
                "source": SOURCE,
                "act_number": ACT_NUMBER,
                "edition_from": EDITION_FROM,
                "edition_to": EDITION_TO,
            }
            body = []
            continue

        if current is None:
            continue

        if not is_noise(line):
            body.append(line)

    if current is not None:
        current["text"] = "\n".join(body)
        articles.append(current)

    return articles


if __name__ == "__main__":
    lines = load_lines(DATA)
    start, end = find_code_region(lines)
    articles = parse_articles(lines, start, end)

    OUT.write_text(
        json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"parsed {len(articles)} articles -> {OUT}")
