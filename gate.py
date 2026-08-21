"""Decide whether retrieval is strong enough to answer at all."""

# Operating point chosen at hour 15.5 from the threshold sweep, not inherited.
#
# The signal is the cross-encoder relevance score, NOT cosine similarity. Cosine
# could not separate the two sets at all: answerable questions scored 0.3573 to
# 0.5627 and unanswerable ones 0.3246 to 0.6050, fully overlapping. Reranker
# relevance leaves a clean gap -- every answerable question scores at least
# 0.5938, and four of five unanswerable ones score at most 0.4902.
#
# 0.54 is the midpoint of that gap, giving roughly 0.05 of margin on each side
# rather than sitting on an edge.
SIGNAL = "rerank_score"
THRESHOLD = 0.54


def should_answer(results):
    """True if the best cross-encoder relevance clears the threshold.

    max() across candidates rather than results[0], so the decision does not
    depend on ordering. The threshold was swept against this same quantity; a
    threshold only means something next to the signal it was measured on.
    """
    if not results:
        return False
    return max(r[SIGNAL] for r in results) >= THRESHOLD
