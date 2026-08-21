import config
import json
import os
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


RERANK_MODEL = "rerank-2.5"


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


def retrieve(question, k=5, use_rerank=True):
    """
    Turn a text question into an embedding,
    compare it against the corpus,
    and return the k best articles.

    Two scores come back on every result, deliberately named rather than a
    single ambiguous "score":

      cosine_score  how close the question and article vectors are
      rerank_score  how relevant the cross-encoder judged the pair

    They are different quantities on different scales. Collapsing them into one
    field would make it impossible to tell which one any threshold refers to.
    """

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

    # Get the best k article rows
    for row in top_k(scores, k):
        article = ARTICLES[row]

        results.append({
            "article": article["article"],
            "citation": article["citation"],
            "title": article["title"],
            "text": article["text"],
            "cosine_score": float(scores[row]),
            "rerank_score": None,
        })

    if use_rerank:
        results = rerank(question, results, client)

    return results


if __name__ == "__main__":
    question = " ".join(sys.argv[1:])

    if not question:
        raise SystemExit(
            'Usage: python retrieval.py "your question here"'
        )

    for result in retrieve(question, k=5):
        rr = result["rerank_score"]
        print(
            f"rerank {rr:.4f}  cos {result['cosine_score']:.4f}  "
            f"article {result['citation']}: "
            f"{result['title']}"
        )