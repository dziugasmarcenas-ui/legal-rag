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


def retrieve(question, k=5):
    """
    Turn a text question into an embedding,
    compare it against the corpus,
    and return the k best articles.
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
            "score": float(scores[row]),
        })

    return results


if __name__ == "__main__":
    question = " ".join(sys.argv[1:])

    if not question:
        raise SystemExit(
            'Usage: python retrieval.py "your question here"'
        )

    for result in retrieve(question, k=3):
        print(
            f"{result['score']:.4f}  "
            f"article {result['citation']}: "
            f"{result['title']}"
        )