"""Link delegated acts back to the Labour Code articles they implement.

A lawyer starts from an article and asks "what actually applies here?" — the
answer is usually a resolution the article delegates to. The link already exists
in the text: every delegated act names the articles it implements ("parengtas
vadovaujantis Darbo kodekso 139 straipsnio 4 dalimi"). This extracts it.

Built once, stored as data/links.json, and read by the MCP tools. Nothing is
inferred: a link exists only where the act's own text names the article.

    python link_graph.py
"""

import json
import re
import sys

from pathlib import Path

ROOT = Path(__file__).parent
SOURCES = ROOT / "data" / "sources.json"
ARTICLES = ROOT / "data" / "articles.json"
LINKS = ROOT / "data" / "links.json"

# "Darbo kodekso 139 straipsnio", "šio kodekso 126 straipsnyje", "DK 64 str."
REFERENCE = re.compile(
    r"(?:darbo\s+kodekso|šio\s+kodekso|kodekso|DK)\s+"
    r"(\d{1,3}(?:-\d{1,2})?)\s*(?:straipsn\w*|str\.)",
    re.IGNORECASE,
)

# Strasbourg judgments cite Lithuanian provisions in English: "Article 59 of the
# Labour Code". That is textual evidence for an edge, so it is extracted.
CASE_REFERENCE = re.compile(
    r"Article\s+(\d{1,3}(?:-\d{1,2})?)\s+of\s+the\s+(?:Lithuanian\s+)?Labour\s+Code",
    re.IGNORECASE,
)

CASE_SOURCES = ("EŽTT sprendimas",)


def build(articles=None, records=None):
    articles = articles if articles is not None else json.loads(
        ARTICLES.read_text(encoding="utf-8")
    )
    records = records if records is not None else json.loads(
        SOURCES.read_text(encoding="utf-8")
    )
    known = {a["article"] for a in articles}

    links = {}
    for record in records:
        if record["source"] in CASE_SOURCES:
            # Cases are linked by metadata only: title, court, date, URL. The
            # graph does not depend on redistributing judgment text.
            for match in CASE_REFERENCE.finditer(record["text"]):
                identifier = match.group(1)
                if identifier not in known:
                    continue
                entry = links.setdefault(identifier, [])
                if any(e.get("citation") == record["act_title"] for e in entry):
                    continue
                entry.append({
                    "kind": "case",
                    "source": "EŽTT",
                    "citation": record["act_title"],
                    "date": record.get("act_date", ""),
                    "url": record["url"],
                    "act_id": record["act_id"],
                })
            continue

        for match in REFERENCE.finditer(record["text"]):
            identifier = match.group(1)
            if identifier not in known:
                # A reference to an article this edition does not have is a
                # parsing error, not a link. Keep it out of the graph.
                continue
            entry = links.setdefault(identifier, [])
            if any(e["citation"] == record["citation"] for e in entry):
                continue
            entry.append({
                "kind": "provision",
                "source": record["source"],
                "citation": record["citation"],
                "act_id": record["act_id"],
                "url": record["url"],
            })

    edges = sum(len(v) for v in links.values())
    cases = sum(1 for v in links.values() for e in v if e.get("kind") == "case")
    return {
        "generated_by": "link_graph.py",
        "articles_linked": len(links),
        "edges": edges,
        "case_edges": cases,
        "links": links,
    }


def main(argv=None):
    graph = build()
    LINKS.write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{graph['edges']} links across {graph['articles_linked']} articles")
    top = sorted(graph["links"].items(), key=lambda kv: -len(kv[1]))[:8]
    for article, entries in top:
        sources = sorted({e["source"] for e in entries})
        print(f"  article {article}: {len(entries)} provisions from {sources}")
    return 0


def load():
    if not LINKS.exists():
        return {"links": {}, "articles_linked": 0, "edges": 0}
    return json.loads(LINKS.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
