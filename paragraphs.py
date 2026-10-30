"""Split an article into its numbered parts, so a citation can name one.

Lithuanian practice cites "126 straipsnio 2 dalis", not just "126 straipsnis".
An answer that can only name the article points the reader at a page instead of
a provision, so the parts are parsed from the Code's own numbering rather than
invented.

Two artefacts of e-TAR's text extraction are repaired here, both of which are
invisible until you try to cite a part:

- **Flattened superscripts.** Article 3 has a part "2¹" that arrives as the line
  "21.". Sequence position is the only evidence that "21." is not part 21.
- **The annex.** The list of EU directives annexed to the Code arrives inside the
  last article (260), where it is neither part of that article nor citable as
  one. `parse_corpus.py` cuts it off before this module sees the text.

The split is deliberately conservative: a number is accepted as a part only when
it continues the sequence, with the superscript case checked by lookahead. A
numbered line that does not fit stays part of the text it appeared in, because
dropping it would silently lose a provision.
"""

import re


PART = re.compile(r"^(\d{1,2})\.\s+\S")

# A flattened superscript part looks like "21." where part "2" already exists
# and the next part is "3". Nothing else in the Code produces that shape.
SUPERSCRIPT_MARK = "¹"


def _superscript_of(number, previous):
    """Return "2¹" if `number` is the flattened form of previous+"¹", else None."""
    if previous is None:
        return None
    text = str(number)
    base = str(previous).rstrip(SUPERSCRIPT_MARK)
    if text == base + "1":
        return base + SUPERSCRIPT_MARK
    return None


def split_parts(text):
    """Return [{number, id, citation, text}] with an unnumbered part if needed.

    `number` is "1", "2", ..., "2¹", or None for an article with no numbering.
    An unnumbered article yields exactly one part, so callers never need to
    special-case it -- they just get a part whose citation is the article's.
    """
    lines = text.splitlines()
    marks = [
        (index, int(match.group(1)))
        for index, line in enumerate(lines)
        if (match := PART.match(line))
    ]

    accepted = []  # (line_index, display_number)
    expected = 1
    previous = None
    for position, (index, number) in enumerate(marks):
        if number == expected:
            accepted.append((index, str(number)))
            previous = str(number)
            expected += 1
            continue

        superscript = _superscript_of(number, previous)
        if superscript and position + 1 < len(marks):
            # Confirmed only if the sequence resumes at `expected` afterwards.
            if marks[position + 1][1] == expected:
                accepted.append((index, superscript))
                previous = superscript
                continue

    if not accepted:
        return [{"number": None, "id": None, "citation": None,
                 "text": text.strip()}] if text.strip() else []

    parts = []
    lead = "\n".join(lines[: accepted[0][0]]).strip()
    if lead:
        # Text before part 1 belongs to the article, not to any part. It is
        # cited as the article itself.
        parts.append({"number": None, "id": None, "citation": None, "text": lead})

    for i, (index, number) in enumerate(accepted):
        end = accepted[i + 1][0] if i + 1 < len(accepted) else len(lines)
        body = "\n".join(lines[index:end]).strip()
        parts.append({
            "number": number,
            "id": number.replace(SUPERSCRIPT_MARK, "-1"),
            "citation": f"{number} d.",
            "text": body,
        })
    return parts


def parts_with_citations(article_id, parts):
    """Attach the article a part belongs to, for display and for tool output."""
    out = []
    for part in parts:
        if part["number"] is None:
            out.append({**part, "article": article_id,
                        "id": article_id,
                        "citation": f"{article_id} straipsnis"})
        else:
            out.append({**part, "article": article_id,
                        "id": f"{article_id}-{part['id']}",
                        "citation": f"{article_id} str. {part['number']} d."})
    return out
