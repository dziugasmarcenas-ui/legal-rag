"""Build data/vectors.db from the existing JSON + NumPy artifacts.

Migration only: after this runs, retrieval reads the store and ingestion writes
to it. The JSON/NPY pair stays in the repo as the source the migration reads,
but the image no longer needs to carry both.

    python migrate_vectors.py          # build the store, report sizes
    python migrate_vectors.py --check  # also prove signature search == brute force
"""

import json
import sys
import time

from pathlib import Path

import numpy as np

import vector_store

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "sources.json"
VECTORS = ROOT / "embeddings" / "sources.npy"
SIDECAR = ROOT / "embeddings" / "sources.json"


def load():
    records = json.loads(DATA.read_text(encoding="utf-8"))
    matrix = np.load(VECTORS)
    if len(records) != matrix.shape[0]:
        raise SystemExit(f"records {len(records)} != vectors {matrix.shape[0]}")
    return records, matrix


def unique_ids(records):
    """Make chunk ids unique without touching their text.

    The old act id was truncated to eight characters, so TAIS.403977 and
    TAIS.403469 produced the same chunk ids. Row-based retrieval never noticed;
    a keyed store would silently drop one of each colliding pair. The generator
    is fixed; this repairs records that were written before it.
    """
    seen, changed = set(), 0
    out = []
    for record in records:
        identifier = record["id"]
        if identifier in seen:
            n = 2
            while f"{identifier}-{n}" in seen:
                n += 1
            record = {**record, "id": f"{identifier}-{n}"}
            identifier = record["id"]
            changed += 1
        seen.add(identifier)
        out.append(record)
    return out, changed


def brute_force(query, matrix, k):
    query = query / max(np.linalg.norm(query), 1e-9)
    scores = matrix @ query
    return list(np.argsort(scores)[::-1][:k]), scores


def check(store, records, matrix, questions, k=10):
    """Compare store.search() with exhaustive cosine over every chunk."""
    by_id = {r["id"]: i for i, r in enumerate(records)}
    overlaps, exact = [], 0
    for question in questions:
        # A deterministic query vector: use an existing chunk vector plus noise,
        # so the check runs without embedding API calls and still exercises the
        # ranking. Real query vectors have the same geometry.
        rng = np.random.default_rng(abs(hash(question)) % 2**32)
        query = matrix[rng.integers(0, len(matrix))] + 0.05 * rng.standard_normal(matrix.shape[1])

        ids, _ = store.search(query)
        got = ids[:k]

        rows, _ = brute_force(query, matrix, k)
        want = [records[i]["id"] for i in rows]

        overlap = len(set(got) & set(want))
        overlaps.append(overlap / k)
        if got == want:
            exact += 1

    return {
        "questions": len(questions),
        "mean_top10_overlap": round(float(np.mean(overlaps)), 4),
        "identical_order": exact,
    }


def main(argv=None):
    records, matrix = load()
    records, repaired = unique_ids(records)
    if repaired:
        DATA.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"repaired {repaired} duplicate chunk ids in {DATA.name}")

    if vector_store.exists():
        vector_store.DB.unlink()

    store = vector_store.load()
    model = fingerprint = None
    if SIDECAR.exists():
        sidecar = json.loads(SIDECAR.read_text(encoding="utf-8"))
        model = sidecar.get("model")
        fingerprint = sidecar.get("fingerprint")

    started = time.time()
    added, updated, unchanged = store.put_many(records, matrix, model=model)
    if fingerprint:
        store.set_meta("fingerprint", fingerprint)
    elapsed = time.time() - started
    print(f"stored {store.count()} chunks ({added} added) in {elapsed:.1f}s")
    print(f"db size: {vector_store.DB.stat().st_size / 1e6:.1f} MB "
          f"(json+npy: {(DATA.stat().st_size + VECTORS.stat().st_size) / 1e6:.1f} MB)")

    # A second pass must change nothing: that is what makes incremental ingest
    # safe to run on every deploy.
    added2, updated2, unchanged2 = store.put_many(records, matrix)
    print(f"second pass: added={added2} updated={updated2} unchanged={unchanged2}")
    if added2 or updated2:
        print("ERROR: second pass rewrote rows; content_hash is unstable")
        return 1

    if "--check" in (argv or sys.argv[1:]):
        questions = [f"q{i}" for i in range(25)]
        report = check(store, records, matrix, questions)
        print("parity:", report)
        if report["mean_top10_overlap"] < 1.0:
            print("WARNING: signature prefilter lost a true neighbour")

    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
