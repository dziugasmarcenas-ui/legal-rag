"""Deploy-safe vector store: SQLite, binary signatures, incremental ingest.

The corpus used to ship as two artifacts -- `data/sources.json` (13 MB) and
`embeddings/sources.npy` (34 MB) -- both loaded whole into memory at import.
That is fine at 117 acts and impossible at 95,000 (tens of GB of floats, all
resident).

The store keeps the same information in one SQLite file and answers the only
question retrieval asks: *which chunks are closest to this query?*

Two-level search:
  1. packed sign bits (1 bit per dimension, 128 bytes per chunk) rank every
     chunk cheaply; memory for 8,700 chunks is ~1 MB instead of 34 MB;
  2. the shortlist is re-scored with its exact float32 vectors, so the ranking
     the reranker sees is real cosine similarity, not the approximation.

Sign bits are only a filter. What that costs is measured, not assumed:
`migrate_vectors.py --check` compares against exhaustive cosine, and the served
evaluation re-runs the published benchmark through both paths.

Incremental ingest is the other half: rows are keyed by a stable chunk id and
hashed by content, so re-ingestion reuses vectors for unchanged chunks and
embeds only what changed.
"""

import hashlib
import json
import sqlite3
import threading

from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
DB = ROOT / "data" / "vectors.db"

DIM = 1024
# Candidates re-scored exactly per query. 1,000 of 8,700 costs ~4 MB of reads and
# recovers the true top-10 about 99% of the time; 200 lost one neighbour in 25.
DEFAULT_CANDIDATES = 1000

POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)

COLUMNS = (
    "id", "kind", "source", "act_id", "act_title", "authority", "act_date",
    "citation", "title", "text", "url", "annex", "chapter", "ref",
    "valid_from", "valid_to", "content_hash",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,
    source       TEXT NOT NULL,
    act_id       TEXT,
    act_title    TEXT,
    authority    TEXT,
    act_date     TEXT,
    citation     TEXT NOT NULL,
    title        TEXT NOT NULL,
    text         TEXT NOT NULL,
    url          TEXT,
    annex        TEXT,
    chapter      TEXT,
    ref          TEXT,
    valid_from   TEXT,
    valid_to     TEXT,
    content_hash TEXT NOT NULL,
    vector       BLOB NOT NULL,
    signature    BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_kind ON chunks(kind);
CREATE INDEX IF NOT EXISTS chunks_source ON chunks(source);
CREATE INDEX IF NOT EXISTS chunks_hash ON chunks(content_hash);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def content_hash(record):
    """Stable identity of the embeddable content (title + text)."""
    payload = json.dumps(
        [record["title"], record["text"]], ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def signature(vector):
    """One bit per dimension: sign of the float. 1024 bits -> 128 bytes."""
    return np.packbits(np.asarray(vector, dtype=np.float32) > 0).tobytes()


def synchronized(method):
    """Serialize access to the one connection shared by API worker threads."""

    def wrapper(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)

    wrapper.__name__ = method.__name__
    return wrapper


def _record_from_row(row):
    data = dict(zip(COLUMNS, row))
    data.pop("content_hash")
    return data


class Store:
    def __init__(self, path=DB):
        self.path = Path(path)
        # FastAPI runs sync endpoints in a worker thread, so the process-wide
        # store is used from several threads. One connection with serialized
        # access is the supported pattern; a per-thread connection would leak.
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.lock = threading.RLock()
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self):
        self.connection.close()

    def _fetchall(self, sql, params=()):
        with self.lock:
            return self.connection.execute(sql, params).fetchall()

    def _execute(self, sql, params=()):
        with self.lock:
            return self.connection.execute(sql, params)

    # --- writes ---------------------------------------------------------
    @synchronized
    def put_many(self, records, vectors, model=None):
        """Insert or replace chunks. Returns (added, updated, unchanged)."""
        added = updated = unchanged = 0
        for record, vector in zip(records, vectors):
            digest = content_hash(record)
            existing = self.connection.execute(
                "SELECT content_hash FROM chunks WHERE id = ?", (record["id"],)
            ).fetchone()
            if existing and existing[0] == digest:
                unchanged += 1
                continue
            values = (
                record["id"],
                record.get("kind") or record.get("source", "act"),
                record["source"],
                record.get("act_id", ""),
                record.get("act_title", ""),
                record.get("authority", ""),
                record.get("act_date", ""),
                record["citation"],
                record["title"],
                record["text"],
                record.get("url", ""),
                record.get("annex", ""),
                record.get("chapter", ""),
                record.get("ref", ""),
                record.get("valid_from", ""),
                record.get("valid_to", ""),
                digest,
                np.asarray(vector, dtype=np.float32).tobytes(),
                signature(vector),
            )
            self.connection.execute(
                f"""INSERT INTO chunks ({",".join(COLUMNS)}, vector, signature)
                    VALUES ({",".join("?" * len(COLUMNS))}, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                      {",".join(f"{c}=excluded.{c}" for c in COLUMNS[1:])},
                      vector=excluded.vector, signature=excluded.signature""",
                values,
            )
            if existing:
                updated += 1
            else:
                added += 1
        if model:
            self.set_meta("model", model)
        self.connection.commit()
        return added, updated, unchanged

    @synchronized
    def delete_missing(self, ids):
        keep = set(ids)
        present = [row[0] for row in self.connection.execute("SELECT id FROM chunks")]
        gone = [i for i in present if i not in keep]
        self.connection.executemany("DELETE FROM chunks WHERE id = ?", [(i,) for i in gone])
        self.connection.commit()
        return len(gone)

    @synchronized
    def set_meta(self, key, value):
        self.connection.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        self.connection.commit()

    @synchronized
    def get_meta(self, key, default=None):
        row = self.connection.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    # --- reads ----------------------------------------------------------
    @synchronized
    def count(self):
        return self.connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def model(self):
        return self.get_meta("model")

    @synchronized
    def signature_matrix(self):
        """(N, 128) packed sign bits plus their ids -- ~1 MB at 8,700 chunks.

        id and signature must come from one row scan: `SELECT id` alone can be
        answered from the primary-key index in a different order than `SELECT
        signature` reads the table, which silently mismatches rows.
        """
        rows = self.connection.execute("SELECT id, signature FROM chunks").fetchall()
        if not rows:
            return np.zeros((0, DIM // 8), dtype=np.uint8), []
        ids = [row[0] for row in rows]
        packed = np.frombuffer(b"".join(row[1] for row in rows), dtype=np.uint8)
        return packed.reshape(len(rows), DIM // 8), ids

    @synchronized
    def ids(self):
        return [row[0] for row in self.connection.execute("SELECT id FROM chunks")]

    @synchronized
    def vectors(self, ids):
        """Exact float32 vectors for these ids, in the same order."""
        if not ids:
            return np.zeros((0, DIM), dtype=np.float32)
        marks = ",".join("?" * len(ids))
        rows = self.connection.execute(
            f"SELECT id, vector FROM chunks WHERE id IN ({marks})", ids
        ).fetchall()
        by_id = {i: np.frombuffer(v, dtype=np.float32) for i, v in rows}
        return np.vstack([by_id[i] for i in ids if i in by_id])

    @synchronized
    def records(self, ids):
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = self.connection.execute(
            f"SELECT {','.join(COLUMNS)} FROM chunks WHERE id IN ({marks})", ids
        ).fetchall()
        by_id = {row[0]: _record_from_row(row) for row in rows}
        return [by_id[i] for i in ids if i in by_id]

    @synchronized
    def all_records(self):
        """Every chunk, in insertion order -- for status and evaluation counts."""
        rows = self.connection.execute(
            f"SELECT {','.join(COLUMNS)} FROM chunks ORDER BY rowid"
        ).fetchall()
        return [_record_from_row(row) for row in rows]

    @synchronized
    def vectors_by_hash(self):
        """content_hash -> vector, so ingestion can reuse unchanged embeddings."""
        rows = self.connection.execute("SELECT content_hash, vector FROM chunks")
        out = {}
        for digest, blob in rows:
            out.setdefault(digest, np.frombuffer(blob, dtype=np.float32))
        return out

    @synchronized
    def search(self, query_vector, candidates=DEFAULT_CANDIDATES):
        """Nearest chunk ids: sign-bit shortlist, exact cosine decides."""
        signatures, ids = self.signature_matrix()
        if not ids:
            return [], np.zeros(0, dtype=np.float32)
        query = np.asarray(query_vector, dtype=np.float32)
        query = query / max(float(np.linalg.norm(query)), 1e-9)

        # Hamming distance over packed bits. Multiplying unpacked +/-1 int8
        # arrays overflows int8 and wraps, which ranks noise; this cannot.
        probe = np.packbits(query > 0)
        hamming = POPCOUNT[signatures ^ probe].sum(axis=1)
        take = min(candidates, len(ids))
        shortlist = [ids[i] for i in np.argsort(hamming)[:take]]

        exact = self.vectors(shortlist)
        scores = exact @ query
        order = np.argsort(scores)[::-1]
        return [shortlist[i] for i in order], scores[order]


def exists(path=DB):
    return Path(path).exists()


def load(path=DB):
    return Store(path)
