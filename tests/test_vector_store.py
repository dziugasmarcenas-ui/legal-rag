"""The store must be a drop-in replacement for the arrays it replaces.

Two properties matter: a chunk that has not changed never costs an embedding,
and the cheap signature filter never loses a true neighbour the reranker should
have seen.
"""

import sys

from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]))

import vector_store


def record(identifier, text="text"):
    return {
        "id": identifier,
        "source": "Test aktas",
        "citation": f"Test aktas, {identifier}",
        "title": "Test",
        "text": text,
        "url": "https://example.invalid",
        "valid_from": "2026-01-01",
        "valid_to": "9999-12-31",
        "act_id": "test",
        "act_title": "Test aktas",
    }


def store(tmp_path):
    return vector_store.load(tmp_path / "vectors.db")


def test_roundtrip_keeps_records_and_vectors(tmp_path):
    s = store(tmp_path)
    records = [record("a"), record("b", "kitkas")]
    vectors = np.random.default_rng(1).standard_normal((2, vector_store.DIM)).astype(np.float32)
    added, updated, unchanged = s.put_many(records, vectors)
    assert (added, updated, unchanged) == (2, 0, 0)
    assert s.count() == 2

    back = s.all_records()
    assert [r["id"] for r in back] == ["a", "b"]
    assert back[1]["text"] == "kitkas"
    assert np.allclose(s.vectors(["a"])[0], vectors[0])
    s.close()


def test_a_second_pass_reuses_every_vector(tmp_path):
    s = store(tmp_path)
    records = [record("a"), record("b", "kitkas")]
    vectors = np.random.default_rng(2).standard_normal((2, vector_store.DIM)).astype(np.float32)
    s.put_many(records, vectors)

    cache = s.vectors_by_hash()
    assert len(cache) == 2
    digests = [vector_store.content_hash(r) for r in records]
    assert all(digest in cache for digest in digests)

    added, updated, unchanged = s.put_many(records, vectors)
    assert (added, updated, unchanged) == (0, 0, 2)
    s.close()


def test_changing_one_text_updates_only_that_row(tmp_path):
    s = store(tmp_path)
    vectors = np.random.default_rng(3).standard_normal((2, vector_store.DIM)).astype(np.float32)
    s.put_many([record("a"), record("b")], vectors)

    edited = [record("a"), record("b", "pakeistas tekstas")]
    new_vectors = vectors.copy()
    new_vectors[1] = new_vectors[1] * -1
    added, updated, unchanged = s.put_many(edited, new_vectors)
    assert (added, updated, unchanged) == (0, 1, 1)

    cache = s.vectors_by_hash()
    assert vector_store.content_hash(edited[0]) in cache
    assert vector_store.content_hash(edited[1]) in cache
    s.close()


def test_signature_filter_finds_the_true_nearest_chunks(tmp_path):
    s = store(tmp_path)
    rng = np.random.default_rng(4)
    vectors = rng.standard_normal((400, vector_store.DIM)).astype(np.float32)
    s.put_many([record(f"c{i}") for i in range(400)], vectors)

    for _ in range(10):
        query = vectors[rng.integers(0, 400)] + 0.05 * rng.standard_normal(vector_store.DIM)
        normalised = query / np.linalg.norm(query)
        true_top = [f"c{i}" for i in np.argsort(vectors @ normalised)[::-1][:5]]

        ids, _ = s.search(query)
        assert set(ids[:5]) == set(true_top)
    s.close()


def test_delete_missing_removes_repealed_chunks(tmp_path):
    s = store(tmp_path)
    vectors = np.random.default_rng(5).standard_normal((3, vector_store.DIM)).astype(np.float32)
    s.put_many([record("a"), record("b"), record("c")], vectors)

    assert s.delete_missing(["a", "c"]) == 1
    assert s.ids() == ["a", "c"]
    s.close()
