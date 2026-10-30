"""MCP surface over the Labour Code retriever.

The host model writes the prose; this server supplies evidence, citations and an
answerability verdict. That division is deliberate: the host already has a good
model and the conversation, and what it cannot invent is a verified article ID.

Two transports, one server:

    python mcp_server.py                  # stdio, for local desktop clients
    mounted at /mcp in main.py            # streamable HTTP, for remote connectors

The tools are the product, so they are written to be composable rather than to
be convenient: every result carries the edition it came from, an explicit
`above_gate` per article, and the citation as a string the host can copy
verbatim. Nothing here writes a citation the retriever did not return.
"""

import os
import sys

from typing import Literal

from mcp.server.auth.settings import (
    AuthSettings,
    ClientRegistrationOptions,
    RevocationOptions,
)
from mcp.server.mcpserver import MCPServer

import answer
import config
import edition
import gate
import history
import llm
import oauth
import paragraphs
import retrieval

config.load_env_file()

DISCLAIMER = (
    "Information retrieval over one consolidated edition of the Lithuanian "
    "Labour Code. Not legal advice; verify against e-TAR before relying on it."
)

# OAuth is enabled by setting OAUTH_PASSWORD. Without it the static MCP_TOKEN
# path stays in use, so a local run never publishes an open authorization server.
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8000").rstrip("/")
OAUTH = oauth.build()

AUTH = (
    AuthSettings(
        issuer_url=PUBLIC_URL,
        # One resource, one audience: the tokens cannot be replayed elsewhere,
        # and there is nothing to validate them against but this URL.
        resource_server_url=f"{PUBLIC_URL}/mcp",
        validate_token_resource=False,
        service_documentation_url=f"{PUBLIC_URL}/",
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["legal:read"],
            default_scopes=["legal:read"],
        ),
        revocation_options=RevocationOptions(enabled=True),
    )
    if OAUTH
    else None
)

mcp = MCPServer(
    name="legal-rag",
    title="Lithuanian Labour Code",
    version="0.1.0",
    auth=AUTH,
    auth_server_provider=OAUTH,
    instructions=(
        "Retrieval over the consolidated Lithuanian Labour Code (Darbo kodeksas).\n\n"
        "Use search_labour_code to find the articles that govern a situation, "
        "get_article to read one in full, and ask_labour_code when the user wants a "
        "written answer instead of evidence.\n\n"
        "Cite the `citation` value verbatim in the form [X straipsnis]. If every "
        "result has `above_gate` false, the Code does not appear to cover the "
        "question: say so instead of answering from general knowledge. If "
        "`corpus.edition_expired` is true, qualify the answer with the edition date."
    ),
)

MAX_K = 10


def _status():
    """What edition this evidence came from. Attached to every tool result."""
    valid_to = retrieval.SIDECAR["edition_to"]
    status = {
        "act": "Lietuvos Respublikos darbo kodeksas",
        "act_number": "XII-2603",
        "articles": len(retrieval.ARTICLES),
        "edition_from": retrieval.SIDECAR["edition_from"],
        "edition_to": valid_to,
        "edition_expired": edition.is_expired(valid_to),
        "source": "e-TAR",
    }
    warning = edition.warning(valid_to)
    if warning:
        status["warning"] = warning
    return status


def _parts(record):
    parts = record.get("parts") or paragraphs.split_parts(record["text"])
    return paragraphs.parts_with_citations(record["article"], parts)


def _source(result):
    score = result["rerank_score"]
    return {
        "article": result["article"],
        "citation": result["citation"],
        "title": result["title"],
        # Parts, not a flat blob: an answer that names "126 str. 2 d." is worth
        # more than one that names the article and leaves the reader to find it.
        "parts": _parts(result),
        "cosine_score": round(result["cosine_score"], 4),
        "rerank_score": round(score, 4) if score is not None else None,
        "above_gate": score is not None and score >= gate.THRESHOLD,
    }


def _confidence(results):
    return round(max((r["rerank_score"] or 0.0) for r in results), 4) if results else 0.0


def _citation(identifier):
    """How the Code writes the article: 72-1 is 72¹ on the page."""
    return identifier.replace("-", "\u00b9", 1) if "-" in identifier else identifier


def _indexed_edition():
    return {
        "valid_from": retrieval.SIDECAR["edition_from"],
        "valid_to": retrieval.SIDECAR["edition_to"],
    }


def normalise_article(value):
    """Accept the forms a person or a model actually types.

    "126", "126 straipsnis", "72-1", "72¹" all name an article; "721" is how
    e-TAR flattens the superscript, and it is not a real article number.
    """
    text = str(value).strip().lower()
    for suffix in ("straipsnis", "straipsnio", "str.", "str"):
        text = text.replace(suffix, "")
    text = text.replace("¹", "-1").replace("^1", "-1").strip(" .")
    return text


@mcp.tool()
def corpus_info() -> dict:
    """What this server covers: edition window, article count, models, threshold.

    Call this first when a question depends on whether the law is current, or
    when you need to tell the user how authoritative an answer can be.
    """
    return {
        "corpus": _status(),
        "embedding_model": retrieval.SIDECAR["model"],
        "rerank_model": retrieval.RERANK_MODEL,
        "abstention_threshold": gate.THRESHOLD,
        "threshold_signal": gate.SIGNAL,
        "history": (
            {
                "available": True,
                **history.coverage(),
                "note": "get_article accepts as_of_date within this range; "
                        "retrieval is indexed on the edition in force today",
            }
            if history.available()
            else {"available": False}
        ),
        "known_gaps": [
            "one consolidated edition only; historical or future editions are not served",
            "articles 85-88 are repealed in this edition and are absent",
            "questions that the Code delegates to another act (e.g. civil procedure) "
            "retrieve the delegating article, which is relevant but not sufficient",
        ],
        "disclaimer": DISCLAIMER,
    }


@mcp.tool()
def search_labour_code(query: str, k: int = 5, as_of_date: str | None = None) -> dict:
    """Find Labour Code articles by meaning, ranked, with their relevance scores.

    Use this for questions about Lithuanian employment law: leave, working time,
    pay, termination, notice, probation, discrimination, safety. Search in
    Lithuanian works best; the corpus is Lithuanian and so are the citation
    numbers.

    `above_gate` is the server's own judgement of whether the strongest result
    is strong enough to answer from. If every result is false, say the Code does
    not appear to cover the question.
    """
    if as_of_date:
        edition = history.in_force(as_of_date) if history.available() else None
        if edition is None:
            return {
                "error": "out_of_range",
                "message": f"no archived edition covers {as_of_date}",
                "covered": history.coverage() if history.available() else None,
            }

    k = max(1, min(int(k), MAX_K))
    results = retrieval.retrieve(
        query, k=k, candidates=max(k, retrieval.SERVED_CANDIDATES),
        as_of_date=as_of_date,
    )
    return {
        "query": query,
        "results": [_source(r) for r in results],
        "confidence": _confidence(results),
        "answerable": gate.should_answer(results),
        # Articles the question named explicitly. They are pinned first, but
        # the answerability gate still judges the evidence on its merits.
        "referenced": retrieval.referenced_articles(query),
        "as_of_date": as_of_date,
        "edition": (
            results[0].get("edition") if results and results[0].get("edition")
            else _indexed_edition()
        ),
        "corpus": _status(),
        "disclaimer": DISCLAIMER,
    }


@mcp.tool()
def get_article(article: str, as_of_date: str | None = None) -> dict:
    """Read one article in full, by number -- "126", "72-1" or "72¹".

    Pass `as_of_date` (YYYY-MM-DD) to read the article **as it stood then**.
    Employment disputes are about the law when the event happened, and the text
    of the same article changes over time. The archive covers 2017-07-01
    onwards; dates outside it are refused rather than silently served today's
    text.
    """
    wanted = normalise_article(article)

    if as_of_date:
        if not history.available():
            return {"error": "history_unavailable",
                    "message": "no edition archive on this deployment"}
        edition = history.in_force(as_of_date)
        if edition is None:
            return {
                "error": "out_of_range",
                "message": f"no archived edition covers {as_of_date}",
                "covered": history.coverage(),
            }
        version = history.article_as_of(wanted, as_of_date)
        if version is None:
            return {
                "error": "not_in_force",
                "message": f"article {wanted} was not in force on {as_of_date}",
                "edition": edition,
            }
        return {
            "article": wanted,
            "citation": _citation(wanted),
            "title": version["title"],
            "text": version["text"],
            "parts": paragraphs.parts_with_citations(
                wanted, paragraphs.split_parts(version["text"])
            ),
            "as_of_date": as_of_date,
            "edition": edition,
            "corpus": _status(),
            "disclaimer": DISCLAIMER,
        }

    for record in retrieval.ARTICLES:
        if record["article"] == wanted:
            return {
                "article": record["article"],
                "citation": record["citation"],
                "title": record["title"],
                "text": record["text"],
                "parts": _parts(record),
                "edition": _indexed_edition(),
                "corpus": _status(),
                "disclaimer": DISCLAIMER,
            }
    return {
        "error": "not_found",
        "message": f"no article {article!r} in this edition",
        "valid_articles": f"{len(retrieval.ARTICLES)} articles; ids look like 126 or 72-1",
        "corpus": _status(),
    }


@mcp.tool()
def ask_labour_code(question: str, lang: Literal["lt", "en"] = "lt") -> dict:
    """Answer a Lithuanian employment-law question from retrieved articles only.

    The prose comes from a language model, but the `sources` are the articles
    the retriever returned, and the citation numbers are attached here -- the
    model cannot introduce one. Below the confidence gate the tool refuses
    instead of guessing, and still returns what it looked at.
    """
    results = retrieval.retrieve(question)
    sources = [_source(r) for r in results]
    confidence = _confidence(results)
    status = _status()

    if not gate.should_answer(results):
        return {
            "answer": answer.REFUSAL[lang],
            "refused": True,
            "refusal_reason": "below_confidence_threshold",
            "confidence": confidence,
            "sources": sources,
            "corpus": status,
            "disclaimer": DISCLAIMER,
        }

    try:
        text = answer.generate(question, results, lang)
    except llm.ProviderUnavailable as error:
        return {
            "answer": None,
            "error": "provider_unavailable",
            "message": str(error),
            "refused": False,
            "confidence": confidence,
            "sources": sources,
            "corpus": status,
            "disclaimer": DISCLAIMER,
        }

    return {
        "answer": text,
        "refused": False,
        "confidence": confidence,
        "confidence_signal": "max_" + gate.SIGNAL,
        "sources": sources,
        "corpus": status,
        "disclaimer": DISCLAIMER,
    }


if OAUTH is not None:
    @mcp.custom_route("/oauth/consent", methods=["GET", "POST"])
    async def oauth_consent(request):
        """The one human step in the flow: prove you are the operator."""
        return await OAUTH.consent_response(request)


# Mounted at /mcp by main.py. The root path is "/" so the mount point, not the
# sub-app, decides the URL.
asgi_app = mcp.streamable_http_app(streamable_http_path="/")


def main(argv=None):
    transport = "stdio"
    args = sys.argv[1:] if argv is None else argv
    if "--http" in args:
        transport = "streamable-http"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
