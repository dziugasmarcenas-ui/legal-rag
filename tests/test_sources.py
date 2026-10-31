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
    if matrix is None:  # served from the SQLite store
        assert retrieval.vector_index().count() == len(records)
    else:
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


def test_a_merely_relevant_act_does_not_bypass_the_gate(monkeypatch):
    """0.699 was measured on an unrelated question; the act bar is 0.78."""
    delegated = {
        "article": None, "citation": "Nutarimas Nr. 496, 5 p.", "title": "t",
        "text": "x", "url": "u", "source": "Nutarimas Nr. 496",
        "cosine_score": 0.5, "rerank_score": 0.70,
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


def test_an_institution_answer_can_unblock_a_question_the_code_does_not_cover():
    import gate

    code_weak = {"article": "48", "source": "Darbo kodeksas", "rerank_score": 0.41}
    explanation = {"article": None, "source": "SADM paaiškinimas", "rerank_score": 0.91}
    assert gate.should_answer_any([code_weak, explanation]) is True


def test_a_merely_relevant_explanation_does_not_bypass_the_gate():
    """Measured: unrelated questions reached 0.79 on explanations; 0.85 separates."""
    import gate

    code_weak = {"article": "48", "source": "Darbo kodeksas", "rerank_score": 0.41}
    explanation = {"article": None, "source": "VDI paaiškinimas", "rerank_score": 0.79}
    assert gate.should_answer_any([code_weak, explanation]) is False


def test_a_confident_act_can_answer_where_the_code_is_silent():
    import gate

    act = {"article": None, "source": "Nutarimas Nr. 496", "rerank_score": 0.82}
    assert gate.should_answer_any([act]) is True


def test_sodra_navigation_and_cookies_are_not_content():
    import ingest_sodra

    assert not ingest_sodra.is_content(
        "Gauti nedarbo išmoką – „Sodra“ Su darbo santykiais susijusios išmokos ..."
    )
    assert not ingest_sodra.is_content(
        "Statistiniai (analitiniai) slapukai analizuoja svetainės lankytojų elgseną"
    )
    assert ingest_sodra.is_content(
        "Nedarbo išmoka skiriama asmeniui, kuris yra įregistruotas bedarbiu "
        "Užimtumo tarnyboje ir turi reikiamą nedarbo socialinio draudimo stažą."
    )


def test_sodra_sitemap_pages_are_ingested_with_a_citable_source():
    records, _ = retrieval.source_index()
    sodra = [r for r in records if r["source"] == "Sodra paaiškinimas"]
    assert len(sodra) >= 200
    assert all("Sodra paaiškinimas" in r["citation"] for r in sodra)
    assert all(r["url"].startswith("https://sodra.lt/") for r in sodra)


def test_a_parliamentary_record_can_answer_what_was_debated():
    import gate

    code_weak = {"article": "184", "source": "Darbo kodeksas", "rerank_score": 0.38}
    record = {"article": None, "source": "Seimo stenogramos", "rerank_score": 0.86}
    assert gate.should_answer_any([code_weak, record]) is True


def test_a_weak_parliamentary_fragment_does_not_decide():
    import gate

    code_weak = {"article": "184", "source": "Darbo kodeksas", "rerank_score": 0.38}
    record = {"article": None, "source": "Seimo stenogramos", "rerank_score": 0.80}
    assert gate.should_answer_any([code_weak, record]) is False


def test_no_repealed_act_is_being_served():
    """e-seimas says NEGALIOJA for these; serving their text as current is wrong."""
    import json

    repealed = json.loads(
        (Path(__file__).parents[1] / "data" / "repealed_ids.json").read_text(encoding="utf-8")
    )
    records, _ = retrieval.source_index()
    serving = {r["act_id"] for r in records if r["act_id"] in repealed}
    assert serving == set(), f"repealed acts still indexed: {sorted(serving)}"


def test_mcp_lists_every_source_family_without_gaps_or_overlaps():
    """A client that only knows about the Code will never ask for the rest."""
    out = mcp_server.corpus_sources()
    families = {k: v for k, v in out.items() if isinstance(v, dict)}
    assert sum(v["chunks"] for v in families.values()) == out["total_chunks"]
    for name in ("delegated_acts", "institution_answers", "eu_directives",
                 "echr_judgments", "constitutional_court", "seimas_drafts",
                 "seimas_committee", "seimas_transcripts"):
        assert families[name]["chunks"] > 0, name
