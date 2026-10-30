"""The acts the Code delegates to.

Resolution No. 496 is where "how is average pay calculated" actually lives; the
Code only points at it. These tests keep the two roles separate: the resolution
corroborates, the Code decides whether there is an answer.
"""

import json
import sys

from datetime import date

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import mcp_server
import retrieval


def test_the_source_index_loads_the_ingested_act():
    records, matrix = retrieval.source_index()
    assert len(records) > 100
    assert matrix.shape[0] == len(records)
    first = records[0]
    for field in ("citation", "source", "text", "url", "act_id"):
        assert first[field], field


def test_every_chunk_carries_a_citable_reference():
    records, _ = retrieval.source_index()
    for record in records:
        assert record["citation"].startswith(record["source"].split()[0])
        assert record["text"].strip()


def test_source_output_is_shaped_for_the_tool_contract():
    record = {
        "article": None,
        "citation": "Nutarimas Nr. 496, 5 p.",
        "title": "VIDUTINIO DARBO UŽMOKESČIO APSKAIČIAVIMAS",
        "text": "5. ...",
        "url": "https://www.e-tar.lt/",
        "source": "Nutarimas Nr. 496",
        "source_title": "Dėl Lietuvos Respublikos darbo kodekso įgyvendinimo",
        "cosine_score": 0.51,
        "rerank_score": 0.80,
    }
    out = mcp_server._source(record)
    assert out["source"].startswith("Nutarimas")
    assert out["parts"] == []
    assert out["above_gate"] is True


def test_the_gate_ignores_delegated_acts(monkeypatch):
    """A confident resolution must not make an uncovered question answerable."""
    delegated = {
        "article": None, "citation": "Nutarimas Nr. 496, 5 p.", "title": "t",
        "text": "x", "url": "u", "source": "Nutarimas Nr. 496",
        "cosine_score": 0.5, "rerank_score": 0.95,
    }
    code = {
        "article": "44", "citation": "44", "label": "44 straipsnis", "title": "t",
        "text": "x", "parts": [], "cosine_score": 0.3, "rerank_score": 0.30,
    }
    monkeypatch.setattr(mcp_server.retrieval, "retrieve",
                        lambda *a, **k: [code, delegated])
    out = mcp_server.search_labour_code("Kokia bauda už parkavimą?", k=1)
    assert out["answerable"] is False
    assert out["confidence"] == 0.3


def test_every_ingested_act_records_its_validity_window():
    records, _ = retrieval.source_index()
    today = "2026-10-30"
    for record in records:
        assert record["valid_from"] and record["valid_to"]
        assert record["valid_to"] >= today, record["source"]


def test_the_source_eval_set_only_names_ingested_acts():
    set_path = Path(__file__).parents[1] / "eval" / "sources_set.json"
    entries = json.loads(set_path.read_text(encoding="utf-8"))
    records, _ = retrieval.source_index()
    names = {r["source"] for r in records}
    assert entries
    for entry in entries:
        assert entry["expected"] in names, entry


def test_stale_delegated_acts_fail_the_freshness_check(monkeypatch):
    import check_freshness

    healthy = check_freshness.source_acts()
    assert check_freshness.check_source_editions(date(2026, 10, 30)) == 0
    monkeypatch.setattr(
        check_freshness, "source_acts",
        lambda: [{"source": "Nutarimas Nr. 496", "valid_to": "2020-01-01"}],
    )
    assert check_freshness.check_source_editions(date(2026, 10, 30)) == 1
    monkeypatch.setattr(check_freshness, "source_acts", lambda: healthy)
