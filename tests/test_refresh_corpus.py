"""Tests for the corpus refresh's parsing rules, without touching e-TAR.

The network part is deliberately not tested -- what is tested is the part that
has silently broken extractors before: runs, tabs and line breaks inside a Word
paragraph, and the edition header that decides whether the file is even the
right document.
"""

import sys
import zipfile

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import refresh_corpus


DOCUMENT = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>
<w:p><w:r><w:t>Suvestinė redakcija nuo 2026-06-07 iki 2026-10-31</w:t></w:r></w:p>
<w:p><w:r><w:t>1 straipsnis. Paskirtis</w:t></w:r></w:p>
<w:p><w:r><w:t xml:space="preserve">1 dalis </w:t></w:r><w:r><w:t>ir 72 straipsnio 2 dalis</w:t></w:r></w:p>
<w:p><w:r><w:t>LIETUVOS RESPUBLIKOS</w:t><w:br/><w:t>DARBO KODEKSAS</w:t></w:r></w:p>
<w:p><w:r><w:t>Respublikos Prezidentė</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>Dalia Grybauskaitė</w:t></w:r></w:p>
<w:p><w:r><w:t>72-1 straipsnis. Laikinojo įdarbinimo įmonė</w:t></w:r></w:p>
<w:p/>
</w:body>
</w:document>
"""


def build_docx(tmp_path):
    path = tmp_path / "edition.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", DOCUMENT)
    return path.read_bytes()


def test_text_within_runs_is_joined_and_breaks_become_spaces(tmp_path):
    text = refresh_corpus.docx_text(build_docx(tmp_path))
    assert "1 dalis ir 72 straipsnio 2 dalis" in text
    assert "LIETUVOS RESPUBLIKOS DARBO KODEKSAS" in text
    assert "Respublikos Prezidentė Dalia Grybauskaitė" in text


def test_empty_paragraphs_are_dropped(tmp_path):
    lines = refresh_corpus.docx_text(build_docx(tmp_path)).splitlines()
    assert lines[0].startswith("Suvestinė redakcija")
    assert "" not in lines
    assert len(lines) == 6


def test_the_edition_window_is_read_from_the_document():
    start, end = refresh_corpus.edition_window(DOCUMENT)
    assert (start, end) == ("2026-06-07", "2026-10-31")


def test_superscript_articles_keep_their_identifier():
    text = "1 straipsnis. Paskirtis\n72-1 straipsnis. Įmonė\n72 straipsnis. Kita"
    assert refresh_corpus.article_ids(text) == ["1", "72-1", "72"]


def test_whitespace_is_not_a_change():
    """e-TAR uses non-breaking spaces for alignment; they must not force a re-embed."""
    assert refresh_corpus.normalise("a\u00a0b  c\n\n d ") == ["a b c", "d"]


def test_changed_lines_reports_only_real_changes():
    old = "one\ntwo\nthree"
    new = "one\ntwo\nthree"
    changes, old_count, new_count = refresh_corpus.changed_lines(old, new)
    assert changes == [] and old_count == new_count == 3

    changes, _, _ = refresh_corpus.changed_lines(old, "one\nTWO\nthree")
    assert changes == [(1, "two", "TWO")]
