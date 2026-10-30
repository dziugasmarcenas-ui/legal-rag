"""Contract tests for the MCP tools, without a network or a model call.

What is tested is the part the host model will rely on: the citation is the
retriever's, `above_gate` matches the gate, an unknown article is a typed error
rather than empty text, and a refusal still returns what was looked at.
"""

import sys

from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

import gate
import mcp_server


def result(number="126", rerank=0.9, cosine=0.6):
    return {
        "article": number,
        "citation": number,
        "title": "Kasmetinės atostogos",
        "text": "Darbuotojui priklauso 20 darbo dienų kasmetinių atostogų.",
        "cosine_score": cosine,
        "rerank_score": rerank,
    }


def test_article_numbers_are_accepted_in_the_forms_people_type():
    assert mcp_server.normalise_article("126") == "126"
    assert mcp_server.normalise_article("126 straipsnis") == "126"
    assert mcp_server.normalise_article("126 str.") == "126"
    assert mcp_server.normalise_article("72¹") == "72-1"
    assert mcp_server.normalise_article("72-1") == "72-1"


def test_corpus_info_reports_the_edition_and_its_expiry():
    info = mcp_server.corpus_info()
    assert info["corpus"]["articles"] == 257
    assert info["corpus"]["edition_to"] == "2026-10-31"
    assert isinstance(info["corpus"]["edition_expired"], bool)
    assert info["abstention_threshold"] == gate.THRESHOLD
    assert "not legal advice" in info["disclaimer"].lower()


def test_get_article_returns_the_loaded_text_or_a_typed_error():
    found = mcp_server.get_article("72¹")
    assert found["citation"] == "72¹"
    assert found["text"]

    missing = mcp_server.get_article("999")
    assert missing["error"] == "not_found"
    assert "corpus" in missing


def test_search_marks_gate_outcomes_per_article(monkeypatch):
    monkeypatch.setattr(
        mcp_server.retrieval, "retrieve",
        lambda *a, **k: [result("126", 0.9), result("128", 0.2)],
    )
    found = mcp_server.search_labour_code("atostogos", k=2)
    assert found["answerable"] is True
    assert [r["above_gate"] for r in found["results"]] == [True, False]
    assert found["results"][0]["citation"] == "126"


def test_search_refuses_to_claim_an_answer_below_the_gate(monkeypatch):
    monkeypatch.setattr(
        mcp_server.retrieval, "retrieve", lambda *a, **k: [result("44", 0.2)]
    )
    found = mcp_server.search_labour_code("kokios baudos už parkavimą", k=1)
    assert found["answerable"] is False
    assert found["results"][0]["above_gate"] is False


def test_ask_refuses_below_the_gate_and_still_shows_sources(monkeypatch):
    monkeypatch.setattr(
        mcp_server.retrieval, "retrieve", lambda *a, **k: [result("44", 0.1)]
    )
    monkeypatch.setattr(
        mcp_server.answer, "generate",
        lambda *a, **k: pytest.fail("the model must not be called on a refusal"),
    )
    out = mcp_server.ask_labour_code("Kokia bauda už parkavimą?")
    assert out["refused"] is True
    assert out["refusal_reason"] == "below_confidence_threshold"
    assert len(out["sources"]) == 1


def test_ask_survives_a_provider_outage(monkeypatch):
    monkeypatch.setattr(
        mcp_server.retrieval, "retrieve", lambda *a, **k: [result("126", 0.9)]
    )

    def boom(*a, **k):
        raise mcp_server.llm.ProviderUnavailable("openai: no key")

    monkeypatch.setattr(mcp_server.answer, "generate", boom)
    out = mcp_server.ask_labour_code("Kiek dienų atostogų?")
    assert out["error"] == "provider_unavailable"
    assert out["answer"] is None
    assert len(out["sources"]) == 1
