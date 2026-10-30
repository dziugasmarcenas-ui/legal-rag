"""The API may not serve a different pipeline than the one that was measured.

There is exactly one place the candidate count lives (`retrieval.SERVED_*`).
This test proves the API does not override it: the route must call
`retrieval.retrieve()` with no arguments, so changing the served configuration
changes both the product and the benchmark.

The generation call is stubbed -- this is a test about wiring, not about prose,
and it must not spend money or need a key.
"""

import sys

from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi.testclient import TestClient

import main
import retrieval


def article(number="126", rerank=0.9):
    return {
        "article": number,
        "citation": number,
        "title": "Kasmetinės atostogos",
        "text": "Darbuotojui priklauso 20 darbo dienų kasmetinių atostogų.",
        "cosine_score": 0.6,
        "rerank_score": rerank,
    }


@pytest.fixture
def captured(monkeypatch):
    seen = {}

    def fake_retrieve(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return [article()]

    monkeypatch.setattr(main.retrieval, "retrieve", fake_retrieve)
    monkeypatch.setattr(main, "generate_answer", lambda *a, **k: "Atsakymas [126 straipsnis].")
    return seen


def test_chat_does_not_override_the_served_configuration(captured):
    client = TestClient(main.app)
    response = client.post("/chat", json={"question": "Kiek dienų kasmetinių atostogų?"})

    assert response.status_code == 200
    assert response.json()["refused"] is False
    assert captured["args"] == ("Kiek dienų kasmetinių atostogų?",)
    assert captured["kwargs"] == {}, (
        "main.py passed retrieval overrides; the served configuration must come "
        "from retrieval.SERVED_* so it cannot drift from the benchmark"
    )


def test_the_served_configuration_reranks_more_than_it_shows():
    """Reranking what you then show is not reranking; it is reordering a shortlist."""
    assert retrieval.SERVED_CANDIDATES > retrieval.SERVED_K


def test_article_references_are_recognised_in_the_forms_people_type():
    assert retrieval.referenced_articles("126 straipsnis") == ["126"]
    assert retrieval.referenced_articles("Kas yra DK 126 straipsnyje?") == ["126"]
    assert retrieval.referenced_articles("72-1 straipsnis") == ["72-1"]
    assert retrieval.referenced_articles("72¹ straipsnis") == ["72-1"]
    assert retrieval.referenced_articles("kiek atostogų pagal 126 str.") == ["126"]


def test_ordinary_questions_name_no_article_and_are_left_to_similarity():
    assert retrieval.referenced_articles("Kiek dienų kasmetinių atostogų man priklauso?") == []
    assert retrieval.referenced_articles("Darbdavys nemoka algos du mėnesius") == []


def test_the_frozen_benchmark_does_not_name_articles():
    """The reference shortcut must not be able to move a published number."""
    import json

    golden = json.loads(
        (Path(__file__).parents[1] / "eval" / "golden_set.json").read_text(encoding="utf-8")
    )
    for entry in golden:
        assert retrieval.referenced_articles(entry["question"]) == [], entry["id"]
