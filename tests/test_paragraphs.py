"""Part-level citations are the difference between pointing at a page and at a rule.

The parser is conservative on purpose: a numbered line that does not continue
the sequence stays in the text it appeared in, because silently dropping a
provision would be worse than citing one level too high.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import paragraphs

SIMPLE = """1. Pirma dalis.
2. Antra dalis.
3. Trečia dalis."""


def test_numbered_parts_are_split_in_order():
    parts = paragraphs.split_parts(SIMPLE)
    assert [p["number"] for p in parts] == ["1", "2", "3"]
    assert [p["citation"] for p in parts] == ["1 d.", "2 d.", "3 d."]
    assert parts[1]["text"].startswith("2.")


def test_flattened_superscript_part_is_repaired():
    """e-TAR writes "2¹" as "21."; the sequence is the only evidence."""
    text = "1. Pirma.\n2. Antra.\n21. Papildyta dalis.\n3. Trečia."
    parts = paragraphs.split_parts(text)
    assert [p["number"] for p in parts] == ["1", "2", "2¹", "3"]
    assert parts[2]["id"] == "2-1"


def test_a_number_that_does_not_continue_the_sequence_is_kept_in_the_text():
    """A numbered list inside a part must not become a fake citation."""
    text = "1. Pirma dalis.\n2. Šioje dalyje išvardyta:\n5. ne numeris\n6. ne numeris"
    parts = paragraphs.split_parts(text)
    assert [p["number"] for p in parts] == ["1", "2"]
    assert "5. ne numeris" in parts[1]["text"]


def test_unnumbered_text_is_one_part_cited_as_the_article():
    parts = paragraphs.split_parts("Vienas nepadalintas sakinys.")
    assert len(parts) == 1
    assert parts[0]["number"] is None

    cited = paragraphs.parts_with_citations("17", parts)
    assert cited[0]["citation"] == "17 straipsnis"
    assert cited[0]["id"] == "17"


def test_text_before_part_one_is_kept_and_cited_as_the_article():
    text = "Įžanginis sakinys.\n1. Pirma dalis.\n2. Antra."
    parts = paragraphs.split_parts(text)
    assert parts[0]["number"] is None
    assert parts[0]["text"] == "Įžanginis sakinys."
    assert [p["number"] for p in parts[1:]] == ["1", "2"]


def test_part_citations_name_article_and_part():
    parts = paragraphs.split_parts(SIMPLE)
    cited = paragraphs.parts_with_citations("126", parts)
    assert cited[0]["citation"] == "126 str. 1 d."
    assert cited[0]["id"] == "126-1"


def test_the_loaded_corpus_reconstructs_from_its_parts():
    """The parts are a view of the text, not a second copy that can drift."""
    import json

    articles = json.loads(
        (Path(__file__).parents[1] / "data" / "articles.json").read_text(encoding="utf-8")
    )
    for article in articles:
        joined = [
            line
            for part in article["parts"]
            for line in part["text"].splitlines()
            if line.strip()
        ]
        original = [line for line in article["text"].splitlines() if line.strip()]
        assert joined == original, article["article"]
