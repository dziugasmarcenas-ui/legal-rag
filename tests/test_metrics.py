"""Unit tests for the retrieval and abstention metrics.

Synthetic cases only -- no corpus, no API, no model. The point is to prove the
arithmetic is right independently of whether retrieval is any good.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "eval"))

import metrics


RESULTS = [
    # correct article at rank 1
    {"id": 1, "expected": ["126"], "retrieved": ["126", "128", "127", "129", "130"],
     "scores": [0.61, 0.5, 0.4, 0.3, 0.2]},
    # correct article at rank 3
    {"id": 2, "expected": ["132"], "retrieved": ["133", "214", "132", "1", "2"],
     "scores": [0.35, 0.3, 0.28, 0.2, 0.1]},
    # two expected articles, the second one hits at rank 4
    {"id": 3, "expected": ["57", "64"], "retrieved": ["25", "44", "3", "64", "9"],
     "scores": [0.48, 0.4, 0.3, 0.2, 0.1]},
    # outright miss
    {"id": 4, "expected": ["999"], "retrieved": ["1", "2", "3", "4", "5"],
     "scores": [0.52, 0.4, 0.3, 0.2, 0.1]},
]


def test_hit_at_k_respects_the_cutoff():
    assert metrics.hit_at_k(RESULTS[1], 1) is False
    assert metrics.hit_at_k(RESULTS[1], 3) is True


def test_any_expected_article_counts_as_a_hit():
    """Question 3 expects 57 or 64; only 64 was retrieved, and that is enough."""
    assert metrics.hit_at_k(RESULTS[2], 5) is True
    assert metrics.hit_at_k(RESULTS[2], 3) is False


def test_a_miss_never_hits():
    assert not any(metrics.hit_at_k(RESULTS[3], k) for k in (1, 3, 5))


def test_recall_at_k_increases_with_k():
    assert metrics.recall_at_k(RESULTS, 1) == 0.25
    assert metrics.recall_at_k(RESULTS, 3) == 0.5
    assert metrics.recall_at_k(RESULTS, 5) == 0.75


def test_empty_results_do_not_divide_by_zero():
    assert metrics.recall_at_k([], 3) == 0.0
    assert metrics.correct_refusal_rate([], 0.5) == 0.0
    assert metrics.false_refusal_rate([], 0.5) == 0.0


def test_refusal_uses_the_top_score_and_the_same_boundary_as_the_gate():
    """gate.should_answer uses >=, so refused() must use < or the reported
    numbers would describe a different system than the one deployed."""
    assert metrics.refused({"scores": [0.49]}, 0.5) is True
    assert metrics.refused({"scores": [0.50]}, 0.5) is False


def test_refusal_rates_move_in_opposite_directions():
    unanswerable = [{"scores": [0.32]}, {"scores": [0.61]}]
    answerable = [{"scores": [0.36]}, {"scores": [0.56]}]
    # raising the threshold refuses more of both
    assert metrics.correct_refusal_rate(unanswerable, 0.4) == 0.5
    assert metrics.correct_refusal_rate(unanswerable, 0.7) == 1.0
    assert metrics.false_refusal_rate(answerable, 0.4) == 0.5
    assert metrics.false_refusal_rate(answerable, 0.7) == 1.0
