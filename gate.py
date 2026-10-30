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


# Institution answers are not the Code, but they are the institution's own
# reading of it. A question about a social benefit is not in the Code at all, so
# gating only on the Code refuses questions the ministry has answered.
EXPLANATION_SOURCES = ("VDI paaiškinimas", "SADM paaiškinimas",
                       "Sodra paaiškinimas")
# Parliamentary record: authoritative for "what was debated", not for the law.
RECORD_SOURCES = ("Seimo stenogramos",)
EXPLANATION_THRESHOLD = 0.85
# Enacted acts other than the Code. Measured: an unrelated question reached 0.699
# on an act, while a question the act answers reached 0.819.
ACT_THRESHOLD = 0.78


def should_answer_any(results):
    """Code first, then institution answers; enacted resolutions never decide alone."""
    code = [r for r in results if r.get("article")]
    if should_answer(code):
        return True
    explanations = [
        r for r in results
        if not r.get("article")
        and r.get("source") in EXPLANATION_SOURCES + RECORD_SOURCES
    ]
    if any((r.get(SIGNAL) or 0.0) >= EXPLANATION_THRESHOLD for r in explanations):
        return True

    acts = [
        r for r in results
        if not r.get("article") and r.get("source") not in EXPLANATION_SOURCES + RECORD_SOURCES
    ]
    return any((r.get(SIGNAL) or 0.0) >= ACT_THRESHOLD for r in acts)


def should_answer(results):
    """True if the best cross-encoder relevance clears the threshold.

    max() across candidates rather than results[0], so the decision does not
    depend on ordering. The threshold was swept against this same quantity; a
    threshold only means something next to the signal it was measured on.
    """
    if not results:
        return False
    return max(r[SIGNAL] for r in results) >= THRESHOLD
