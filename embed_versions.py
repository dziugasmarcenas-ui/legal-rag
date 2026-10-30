"""Embed every archived version of every article, so history is searchable.

`get_article(as_of_date)` can already read the law of a past date, but search
still refused it. Half a feature is worse than none: it teaches the caller that
`as_of_date` is a lie. This builds the second index the archive needs.

One vector per article *version*, not per article. 498 versions of 257 articles
is a 2 MB matrix, and it is what lets "kiek atostogų priklausė 2019 metais"
retrieve the 2019 text rather than today's.

    python embed_versions.py           # cache-aware; no API call if current
    python embed_versions.py --refresh

Outputs:
    embeddings/versions.npy     one row per version
    embeddings/versions.json    sidecar: which version each row is
"""

import hashlib
import json
import sys

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import voyageai

import config

MODEL = "voyage-3"
BATCH_SIZE = 64

ROOT = Path(__file__).parent
HISTORY = ROOT / "data" / "history.json"
VECTORS = ROOT / "embeddings" / "versions.npy"
SIDECAR = ROOT / "embeddings" / "versions.json"


def records():
    """One record per (article, version), in a stable order."""
    data = json.loads(HISTORY.read_text(encoding="utf-8"))
    out = []
    for article in sorted(data["articles"], key=lambda i: (int(i.split("-")[0]), i)):
        for version in data["articles"][article]:
            out.append({
                "article": article,
                "valid_from": version["from"],
                "valid_to": version["to"],
                "title": version["title"],
                "text": version["text"],
            })
    return out


def embedding_input(record):
    return record["title"] + "\n" + record["text"]


def fingerprint(texts):
    digest = hashlib.sha256()
    digest.update(MODEL.encode("utf-8"))
    for text in texts:
        digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def main(argv=None):
    rows = records()
    texts = [embedding_input(r) for r in rows]
    expected = fingerprint(texts)

    if VECTORS.exists() and SIDECAR.exists():
        sidecar = json.loads(SIDECAR.read_text(encoding="utf-8"))
        if sidecar.get("fingerprint") == expected and "--refresh" not in (argv or sys.argv[1:]):
            print(f"version index already current: {sidecar['count']} versions -- no API call made")
            return 0

    client = voyageai.Client(api_key=config.require("VOYAGE_API_KEY"))
    vectors = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        result = client.embed(batch, model=MODEL, input_type="document")
        vectors.extend(result.embeddings)
        print(f"  embedded {min(i + BATCH_SIZE, len(texts))}/{len(texts)}")

    matrix = np.array(vectors, dtype=np.float32)
    np.save(VECTORS, matrix)
    SIDECAR.write_text(json.dumps({
        "model": MODEL,
        "count": int(matrix.shape[0]),
        "dimensions": int(matrix.shape[1]),
        "fingerprint": expected,
        "embedded_at": datetime.now(timezone.utc).isoformat(),
        "versions": rows,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"saved {matrix.shape} to {VECTORS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
