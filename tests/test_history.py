"""The archive is a product claim, so its boundaries are tested.

Three things can go wrong and each is covered here: picking the wrong edition on
a boundary date, serving an article that did not yet exist, and silently
answering a historical question with today's text.
"""

import sys

from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

import history
import mcp_server


def test_the_archive_spans_every_edition_the_portal_publishes():
    assert history.available()
    coverage = history.coverage()
    assert coverage["editions"] == 41
    assert coverage["from"] == "2017-07-01"


def test_editions_are_contiguous():
    """A gap would mean a date on which the tool silently has no law."""
    editions = history.editions()
    for earlier, later in zip(editions, editions[1:]):
        assert earlier["valid_to"] < later["valid_from"], (earlier, later)


def test_the_boundary_day_belongs_to_the_old_edition():
    assert history.in_force("2026-10-31")["valid_from"] == "2026-06-07"


def test_the_next_day_belongs_to_the_new_edition():
    assert history.in_force("2026-11-01")["valid_from"] == "2026-11-01"


def test_an_article_that_did_not_exist_yet_is_absent():
    assert history.article_as_of("72-1", "2017-07-01") is None
    assert history.article_as_of("72-1", "2026-10-30") is not None


def test_the_same_article_reads_differently_across_editions():
    """Article 59 has six versions; if this passes trivially the archive is flat."""
    old = history.article_as_of("59", "2018-01-01")
    new = history.article_as_of("59", "2026-10-30")
    assert old and new
    assert old["text"] != new["text"]
    assert old["to"] < new["from"]


def test_get_article_as_of_returns_the_text_of_that_day():
    old = mcp_server.get_article("59", as_of_date="2018-06-01")
    new = mcp_server.get_article("59")
    assert old["text"] != new["text"]
    assert old["as_of_date"] == "2018-06-01"
    assert old["edition"]["valid_from"] == "2018-01-01"
    assert old["parts"], "historical text is split into parts like the current one"


def test_get_article_refuses_a_date_before_the_archive():
    out = mcp_server.get_article("126", as_of_date="2010-01-01")
    assert out["error"] == "out_of_range"
    assert out["covered"]["from"] == "2017-07-01"


def test_get_article_refuses_an_article_that_was_not_in_force():
    out = mcp_server.get_article("72-1", as_of_date="2017-08-01")
    assert out["error"] == "not_in_force"


def test_search_refuses_a_date_it_cannot_search(monkeypatch):
    """Retrieval is indexed on one edition; claiming otherwise would be a lie."""
    out = mcp_server.search_labour_code("atostogos", as_of_date="2019-01-01")
    assert out["error"] == "out_of_range"
    assert out["indexed_edition"]["valid_from"] == "2026-06-07"


def test_corpus_info_advertises_the_archive():
    info = mcp_server.corpus_info()
    assert info["history"]["available"] is True
    assert info["history"]["editions"] == 41
    assert "as_of_date" in info["history"]["note"]
