"""The citation graph and the status endpoint are claims, so they are tested.

Links must come from the acts' own text: a wrong edge sends a lawyer to a
provision that does not implement the article. Status must tell the truth about
coverage and freshness, not just return 200.
"""

import sys

from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

import link_graph
import main


ARTICLES = [{"article": "139"}, {"article": "126"}, {"article": "226"}]
RECORDS = [
    {
        "citation": "Nutarimas Nr. 496, 1 p.",
        "source": "Nutarimas Nr. 496",
        "act_id": "496",
        "url": "https://www.e-tar.lt/",
        "text": "Aprašas parengtas vadovaujantis Darbo kodekso 139 straipsnio 4 dalimi.",
    },
    {
        "citation": "SADM įsakymas A1-344, 2 p.",
        "source": "SADM įsakymas A1-344",
        "act_id": "a1344",
        "url": "https://www.e-tar.lt/",
        "text": "Vadovaujantis šio kodekso 226 straipsniu ir 999 straipsniu.",
    },
    {
        "citation": "Nutarimas Nr. 496, 9 p.",
        "source": "Nutarimas Nr. 496",
        "act_id": "496",
        "url": "https://www.e-tar.lt/",
        "text": "Nuostata taikoma kartu su 126 straipsniu.",  # no "kodekso" -> no link
    },
]


def test_links_are_extracted_only_where_the_act_names_an_article():
    graph = link_graph.build(ARTICLES, RECORDS)
    assert set(graph["links"]) == {"139", "226"}
    assert graph["links"]["139"][0]["source"] == "Nutarimas Nr. 496"
    assert graph["edges"] == 2


def test_a_reference_to_an_article_outside_the_edition_is_dropped():
    graph = link_graph.build(ARTICLES, RECORDS)
    assert "999" not in graph["links"]


def test_duplicate_citations_are_collapsed():
    records = RECORDS + [RECORDS[0]]
    graph = link_graph.build(ARTICLES, records)
    assert len(graph["links"]["139"]) == 1


def test_get_article_reports_the_acts_that_implement_it():
    out = mcp_get = __import__("mcp_server").get_article("139")
    assert "implemented_by" in out
    assert any(entry["source"] == "Nutarimas Nr. 496" for entry in out["implemented_by"])


def test_status_reports_coverage_freshness_and_measured_quality():
    with TestClient(main.app) as client:
        payload = client.get("/status").json()

    assert payload["code"]["articles"] == 257
    assert payload["delegated_acts"]["acts"] >= 7
    assert payload["delegated_acts"]["chunks"] >= 600
    assert payload["delegated_acts"]["stale"] == []
    assert payload["history"]["editions"] == 41
    assert payload["evals"]["code_served"]["served_hit1"] == 0.92
    assert payload["evals"]["delegated"]["term_rate"] >= 0.9
    assert payload["explanations"]["items"] >= 500
    assert len(payload["explanations"]["institutions"]) >= 2
    assert payload["eu_law"]["directives"] >= 5
    assert payload["echr"]["judgments"] >= 3
    assert payload["links"]["edges"] >= 300
    assert payload["links"]["case_edges"] >= 2
