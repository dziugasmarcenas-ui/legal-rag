"""Embed the parsed articles and persist the vectors to disk.

Input:  data/articles.json
Output: embeddings/corpus.npy   (float32 matrix, one row per article)
        embeddings/corpus.json  (sidecar: what those rows are)

Re-running is cheap: if the sidecar's fingerprint matches the current corpus
and model, the vectors are reused and no API call is made.
"""

import hashlib
import json
import os
import sys

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import voyageai

MODEL = "voyage-3"
BATCH_SIZE = 64

ROOT = Path(__file__).parent
ARTICLES = ROOT / "data" / "articles.json"
VECTORS = ROOT / "embeddings" / "corpus.npy"
SIDECAR = ROOT / "embeddings" / "corpus.json"


def embedding_input(article):
    """The text actually sent to the embedding model.

    Title plus body, not body alone. An article's title is a dense statement
    of its subject ("Kasmetiniu atostogu savoka ir trukme") and real questions
    tend to echo it closely, so including it puts the strongest signal in the
    vector. The title is still stored separately in the record -- this only
    affects what gets embedded.
    """
    return article["title"] + "\n" + article["text"]


def fingerprint(texts):
    """Hash of exactly what we embedded, so a changed corpus is detected."""
    digest = hashlib.sha256()
    digest.update(MODEL.encode("utf-8"))
    for text in texts:
        digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def load_articles():
    return json.loads(ARTICLES.read_text(encoding="utf-8"))


def is_current(expected):
    """True if persisted vectors already match this corpus and model."""
    if not VECTORS.exists() or not SIDECAR.exists():
        return False
    sidecar = json.loads(SIDECAR.read_text(encoding="utf-8"))
    return sidecar.get("corpus_fingerprint") == expected


def embed_documents(client, texts):
    vectors = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        # input_type="document" tells Voyage this text is being stored, not
        # searched with. Queries are embedded with input_type="query" so the
        # two sides of the comparison are prepared consistently.
        result = client.embed(batch, model=MODEL, input_type="document")
        vectors.extend(result.embeddings)
        print(f"  embedded {min(i + BATCH_SIZE, len(texts))}/{len(texts)}")
    return vectors


def main():
    articles = load_articles()
    texts = [embedding_input(a) for a in articles]
    expected = fingerprint(texts)

    if is_current(expected):
        matrix = np.load(VECTORS)
        print(f"vectors already current: {matrix.shape} -- no API call made")
        return

    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        sys.exit(
            "VOYAGE_API_KEY is not set.\n"
            "Export it in this shell, then run this script again:\n"
            "    export VOYAGE_API_KEY='...'"
        )

    print(f"embedding {len(texts)} articles with {MODEL}...")
    client = voyageai.Client(api_key=api_key)
    vectors = embed_documents(client, texts)

    matrix = np.array(vectors, dtype=np.float32)
    if matrix.shape[0] != len(articles):
        raise ValueError(
            f"got {matrix.shape[0]} vectors for {len(articles)} articles"
        )

    VECTORS.parent.mkdir(exist_ok=True)
    np.save(VECTORS, matrix)

    # The sidecar records which article each ROW belongs to, in order. Row
    # order is the only thing binding a vector to its citation; if it ever
    # drifts, retrieval still "works" but every citation is silently wrong.
    # Storing the order explicitly makes that failure checkable.
    SIDECAR.write_text(
        json.dumps(
            {
                "model": MODEL,
                "dimensions": int(matrix.shape[1]),
                "count": int(matrix.shape[0]),
                "corpus_fingerprint": expected,
                "edition_from": articles[0]["edition_from"],
                "edition_to": articles[0]["edition_to"],
                "embedded_at": datetime.now(timezone.utc).isoformat(),
                "article_ids": [a["article"] for a in articles],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"saved {matrix.shape} to {VECTORS}")
    print(f"saved sidecar to {SIDECAR}")


if __name__ == "__main__":
    main()
