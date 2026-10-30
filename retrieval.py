import config
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import voyageai


ROOT = Path(__file__).parent

# Load article metadata
ARTICLES = json.loads(
    (ROOT / "data" / "articles.json").read_text(encoding="utf-8")
)

# Load the 257 × 1024 embedding matrix
VECTORS = np.load(ROOT / "embeddings" / "corpus.npy")

# Load metadata that says which article belongs to each embedding row
SIDECAR = json.loads(
    (ROOT / "embeddings" / "corpus.json").read_text(encoding="utf-8")
)


# Safety check:
# article order must match embedding order
if [a["article"] for a in ARTICLES] != SIDECAR["article_ids"]:
    raise ValueError(
        "articles.json and corpus.npy are out of order -- re-run embed_corpus.py"
    )


def cosine_similarities(query, matrix):
    """
    Compare one query embedding against every article embedding.
    Returns one similarity score per article.
    """

    # Make query vector length = 1
    query = query / np.linalg.norm(query)

    # Compare query against all article vectors
    return matrix @ query


def top_k(scores, k):
    """
    Return the row numbers of the k highest scores,
    best match first.
    """

    # argsort gives lowest -> highest
    ordered = np.argsort(scores)

    # Reverse it: highest -> lowest
    ordered = ordered[::-1]

    # Keep only first k
    return ordered[:k]


# The served configuration, defined once.
#
# `candidates` is how many articles cosine search pulls in. `k` is how many the
# caller sees. Reranking only reorders what it is given, so reranking 3 of them
# is not the same product as reranking 10 and showing 3 -- and the second is what
# the benchmark measured. The API and the eval both call `retrieve()` with no
# arguments, so these two numbers cannot drift between them.
#
# Raising candidates costs one rerank call on a few more short documents, which
# is noise next to the generation call.
SERVED_CANDIDATES = 10
SERVED_K = 3

RERANK_MODEL = "rerank-2.5"

_HISTORY = None


def historical_index():
    """The per-version matrix, loaded once and only if a dated query needs it."""
    global _HISTORY
    if _HISTORY is None:
        sidecar = json.loads(
            (ROOT / "embeddings" / "versions.json").read_text(encoding="utf-8")
        )
        _HISTORY = (
            np.load(ROOT / "embeddings" / "versions.npy"),
            sidecar["versions"],
        )
    return _HISTORY


def select_versions(scores, versions, as_of_date, candidates):
    """Best version of each article that was in force on `as_of_date`.

    One row per article, not per version: an article that changed five times
    must not fill the candidate list with its own history. The kept row is the
    highest-scoring version valid on that date.
    """
    eligible = [
        (float(scores[i]), i)
        for i, version in enumerate(versions)
        if version["valid_from"] <= as_of_date <= version["valid_to"]
    ]
    eligible.sort(reverse=True)

    chosen, seen = [], set()
    for score, index in eligible:
        version = versions[index]
        if version["article"] in seen:
            continue
        seen.add(version["article"])
        chosen.append({**version, "cosine_score": score})
        if len(chosen) >= candidates:
            break
    return chosen


def retrieve_as_of(question, as_of_date, k=SERVED_K, candidates=SERVED_CANDIDATES):
    """Search the law as it stood on `as_of_date`.

    Same embedding model, same reranker, same gate; only the candidate set is
    restricted to versions that were in force. The returned records carry the
    edition window they came from, because a 2019 answer that does not say 2019
    is the failure mode this feature exists to prevent.
    """
    matrix, versions = historical_index()
    client = voyageai.Client(api_key=config.require("VOYAGE_API_KEY"))

    embedded = client.embed([question], model="voyage-3", input_type="query")
    query = np.array(embedded.embeddings[0], dtype=np.float32)
    scores = cosine_similarities(query, matrix)

    rows = select_versions(scores, versions, as_of_date, max(candidates, k))
    if not rows:
        return []

    results = [
        {
            "article": r["article"],
            "citation": r.get("citation") or r["article"],
            "title": r["title"],
            "text": r["text"],
            "parts": [],
            "cosine_score": r["cosine_score"],
            "rerank_score": None,
            "edition": {"valid_from": r["valid_from"], "valid_to": r["valid_to"]},
        }
        for r in rows
    ]

    results = rerank(question, results, client)

    referenced = set(referenced_articles(question))
    if referenced:
        results = (
            [r for r in results if r["article"] in referenced]
            + [r for r in results if r["article"] not in referenced]
        )
    return results[:k]


def rerank(question, results, client):
    """
    Reorder candidates with a cross-encoder.

    The embedding model encodes the question and the article separately, so it
    compares two summaries of meaning. A reranker reads the question and one
    article TOGETHER and scores that pair, which is why it can tell a generic
    procedural article from the situation-specific one that actually governs.

    This only reorders the candidates it is given. It cannot retrieve an article
    that embedding search missed.
    """

    documents = [r["title"] + "\n" + r["text"] for r in results]
    ranking = client.rerank(question, documents, model=RERANK_MODEL)

    ordered = []
    for item in ranking.results:
        result = dict(results[item.index])
        result["rerank_score"] = float(item.relevance_score)
        ordered.append(result)

    return ordered



# "126 straipsnis", "DK 126 str.", "72-1 straipsnyje", "72¹ straipsnis".
#
# An explicit reference is not a search problem. Embedding "126 straipsnis"
# returns articles about numbers and procedures, so the article the user named
# is pulled in directly and ranked by the same reranker as everything else.
# None of the frozen questions name an article, so this changes no measured
# number -- it fixes a failure the benchmark never covered.
ARTICLE_REFERENCE = re.compile(
    r"(\d{1,3})(?:\s*[-\u2013]\s*(\d{1,2})|(\u00b9))?\s*(?:straipsn\w*|str\.?)\b",
    re.IGNORECASE,
)


def referenced_articles(question):
    """Article ids the question names explicitly, in the order named."""
    found = []
    for match in ARTICLE_REFERENCE.finditer(question):
        identifier = match.group(1)
        if match.group(2):
            identifier += "-" + match.group(2)
        elif match.group(3):
            identifier += "-1"
        if identifier not in found:
            found.append(identifier)
    return found


SOURCE_CANDIDATES = 8
SOURCE_SHOWN = 2
# A source chunk has to be genuinely close before it is allowed to compete with
# the Code. Without a floor, every query drags five irrelevant provisions into
# the reranker and can push the governing article out of the answer.
SOURCE_FLOOR = 0.42

_SOURCES = None


def source_index():
    global _SOURCES
    if _SOURCES is None:
        records = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
        matrix = np.load(ROOT / "embeddings" / "sources.npy")
        _SOURCES = (records, matrix)
    return _SOURCES


def source_candidates(query_vector, k=SOURCE_CANDIDATES):
    """Delegated acts: resolutions the Code points at for the actual rule."""
    if not (ROOT / "data" / "sources.json").exists():
        return []
    records, matrix = source_index()
    if not records:
        return []

    scores = cosine_similarities(query_vector, matrix)
    out = []
    for row in top_k(scores, min(k, len(records))):
        if float(scores[row]) < SOURCE_FLOOR:
            continue
        record = records[row]
        out.append({
            "article": None,
            "citation": record["citation"],
            "label": record["citation"],
            "source": record["source"],
            "source_title": record["act_title"],
            "url": record["url"],
            "title": record["title"],
            "text": record["text"],
            "parts": [],
            "cosine_score": float(scores[row]),
            "rerank_score": None,
        })
    return out


def retrieve(question, k=SERVED_K, candidates=SERVED_CANDIDATES, use_rerank=True,
             as_of_date=None):
    """The served retrieval, optionally as of a past date.

    A date inside the loaded edition takes the normal path, so the measured
    numbers and the served results stay identical. Only dates outside it use
    the version index.
    """
    """
    Turn a text question into an embedding,
    compare it against the corpus,
    and return the k best articles.

    `candidates` must be at least `k`; more candidates than that only gives the
    reranker more to reorder, and never changes how many are returned.

    Two scores come back on every result, deliberately named rather than a
    single ambiguous "score":

      cosine_score  how close the question and article vectors are
      rerank_score  how relevant the cross-encoder judged the pair

    They are different quantities on different scales. Collapsing them into one
    field would make it impossible to tell which one any threshold refers to.
    """

    if as_of_date and not (
        SIDECAR["edition_from"] <= as_of_date <= SIDECAR["edition_to"]
    ):
        return retrieve_as_of(question, as_of_date, k=k, candidates=candidates)

    client = voyageai.Client(api_key=config.require("VOYAGE_API_KEY"))

    # Turn the user's question into a 1024-number embedding
    embedded = client.embed(
        [question],
        model="voyage-3",
        input_type="query",
    )

    query = np.array(
        embedded.embeddings[0],
        dtype=np.float32,
    )

    # Get similarity score for every article
    scores = cosine_similarities(query, VECTORS)

    results = []

    # An explicitly named article is taken directly, before similarity ranking.
    by_id = {a["article"]: a for a in ARTICLES}
    for identifier in referenced_articles(question):
        article = by_id.get(identifier)
        if article is None:
            continue
        results.append({
            "article": article["article"],
            "citation": article["citation"],
            "label": f"{article['citation']} straipsnis",
            "title": article["title"],
            "text": article["text"],
            "parts": article.get("parts", []),
            "cosine_score": float(scores[ARTICLES.index(article)]),
            "rerank_score": None,
        })

    # Get the best candidate rows; the reranker decides which k survive.
    for row in top_k(scores, max(candidates, k)):
        article = ARTICLES[row]
        if any(r["article"] == article["article"] for r in results):
            continue

        results.append({
            "article": article["article"],
            "citation": article["citation"],
            "label": f"{article['citation']} straipsnis",
            "title": article["title"],
            "text": article["text"],
            # Derived at parse time; carried through so a caller can cite the
            # part a claim actually rests on, not just the article.
            "parts": article.get("parts", []),
            "cosine_score": float(scores[row]),
            "rerank_score": None,
        })

    # Delegated acts join the same reranker, so the comparison is like-for-like.
    results.extend(source_candidates(query))

    if use_rerank:
        results = rerank(question, results, client)

    # The Code and the acts it delegates to are not peers. The Code decides
    # whether there is an answer at all; a resolution is corroboration shown
    # beside it. Mixing them into one ranking let a provision outrank the
    # governing article and made an off-topic question look answerable, which is
    # exactly the failure the gate exists to prevent.
    code = [r for r in results if r.get("article")]
    delegated = [r for r in results if not r.get("article")]

    # A named article is pinned first. The reranker is judging relevance to the
    # phrasing, and "Kas yra DK 126 straipsnyje?" scores the article about
    # numbers higher than the one the user asked for. When the user names a
    # provision, returning it first is the answer to the request.
    referenced = set(referenced_articles(question))
    if referenced:
        code = (
            [r for r in code if r["article"] in referenced]
            + [r for r in code if r["article"] not in referenced]
        )

    return code[:k] + delegated[:SOURCE_SHOWN]


if __name__ == "__main__":
    question = " ".join(sys.argv[1:])

    if not question:
        raise SystemExit(
            'Usage: python retrieval.py "your question here"'
        )

    for result in retrieve(question, k=5, candidates=10):
        rr = result["rerank_score"]
        print(
            f"rerank {rr:.4f}  cos {result['cosine_score']:.4f}  "
            f"article {result['citation']}: "
            f"{result['title']}"
        )