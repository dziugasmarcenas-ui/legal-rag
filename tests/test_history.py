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
import retrieval


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


def test_search_refuses_a_date_outside_the_archive():
    """Inside the archive history is searchable; outside it, say so."""
    out = mcp_server.search_labour_code("atostogos", as_of_date="2010-01-01")
    assert out["error"] == "out_of_range"
    assert out["covered"]["from"] == "2017-07-01"


def test_corpus_info_advertises_the_archive():
    info = mcp_server.corpus_info()
    assert info["history"]["available"] is True
    assert info["history"]["editions"] == 41
    assert "as_of_date" in info["history"]["note"]


VERSIONS = [
    {"article": "126", "valid_from": "2017-07-01", "valid_to": "2022-07-31",
     "title": "old", "text": "old text"},
    {"article": "126", "valid_from": "2022-08-01", "valid_to": "9999-12-31",
     "title": "new", "text": "new text"},
    {"article": "127", "valid_from": "2017-07-01", "valid_to": "9999-12-31",
     "title": "other", "text": "other text"},
]


def test_select_versions_returns_one_row_per_article():
    """An article with five versions must not fill the candidate list."""
    chosen = retrieval.select_versions([0.9, 0.95, 0.5], VERSIONS, "2019-01-01", 10)
    assert [c["article"] for c in chosen] == ["126", "127"]
    assert chosen[0]["text"] == "old text"


def test_select_versions_skips_versions_not_in_force_then():
    chosen = retrieval.select_versions([0.9, 0.95, 0.5], VERSIONS, "2026-10-30", 10)
    assert [c["text"] for c in chosen if c["article"] == "126"] == ["new text"]


def test_select_versions_is_respects_the_candidate_budget():
    assert len(retrieval.select_versions([0.9, 0.9, 0.5], VERSIONS, "2019-01-01", 1)) == 1


def test_select_versions_returns_nothing_outside_the_archive():
    assert retrieval.select_versions([0.9, 0.9, 0.5], VERSIONS, "2010-01-01", 10) == []


def test_search_passes_the_date_to_retrieval(monkeypatch):
    seen = {}

    def fake_retrieve(*args, **kwargs):
        seen.update(kwargs)
        return [{
            "article": "126", "citation": "126", "title": "t", "text": "1. x",
            "parts": [], "cosine_score": 0.5, "rerank_score": 0.9,
            "edition": {"valid_from": "2017-07-01", "valid_to": "2022-07-31"},
        }]

    monkeypatch.setattr(mcp_server.retrieval, "retrieve", fake_retrieve)
    out = mcp_server.search_labour_code("atostogos", k=1, as_of_date="2019-01-01")
    assert seen["as_of_date"] == "2019-01-01"
    assert out["edition"]["valid_from"] == "2017-07-01"
    assert out["as_of_date"] == "2019-01-01"


def test_a_historical_answer_is_told_which_edition_it_is_answering_from():
    import answer

    prompt = answer.build_prompt(
        "Kiek atostogų?", [{"citation": "126", "title": "T", "text": "x"}],
        edition={"valid_from": "2017-07-01", "valid_to": "2022-07-31"},
    )
    assert "2017-07-01" in prompt and "2022-07-31" in prompt
    assert "galiojo" in prompt

    current = answer.build_prompt(
        "Kiek atostogų?", [{"citation": "126", "title": "T", "text": "x"}]
    )
    assert "galiojo" not in current


def test_ask_passes_the_edition_to_generation(monkeypatch):
    seen = {}

    def fake_retrieve(*args, **kwargs):
        return [{
            "article": "126", "citation": "126", "title": "t", "text": "1. x",
            "parts": [], "cosine_score": 0.5, "rerank_score": 0.9,
            "edition": {"valid_from": "2017-07-01", "valid_to": "2022-07-31"},
        }]

    monkeypatch.setattr(mcp_server.retrieval, "retrieve", fake_retrieve)
    monkeypatch.setattr(
        mcp_server.answer, "generate",
        lambda q, r, lang, edition=None: seen.update(edition=edition) or "atsakymas",
    )
    out = mcp_server.ask_labour_code("Kiek atostogų?", as_of_date="2019-01-01")
    assert seen["edition"]["valid_from"] == "2017-07-01"
    assert out["as_of_date"] == "2019-01-01"
    assert out["edition"]["valid_to"] == "2022-07-31"


def test_ask_refuses_a_date_outside_the_archive():
    out = mcp_server.ask_labour_code("Kiek atostogų?", as_of_date="2010-01-01")
    assert out["error"] == "out_of_range"
