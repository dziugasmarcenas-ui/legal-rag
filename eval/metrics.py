"""Metrics over cached retrieval results. No API calls, no model involved."""


def hit_at_k(result, k):
    """True if any expected article appears in the top k retrieved."""
    top = result["retrieved"][:k]
    for article in result["expected"]:
        if article in top:
            return True
    return False


def recall_at_k(results, k):
    """Fraction of questions where a correct article was in the top k."""
    if not results:
        return 0.0
    hits = 0
    for result in results:
        if hit_at_k(result, k):
            hits += 1
    return hits / len(results)

def refused(result, threshold, key="scores"):
    """True if the gate would decline to answer this question.

    `key` names which score list to read. Cosine similarity and reranker
    relevance are different scales, so a threshold is only meaningful next to
    the signal it was swept against.
    """
    return max(result[key]) < threshold


def correct_refusal_rate(results, threshold, key="scores"):
    """Of UNANSWERABLE questions, the fraction correctly refused. Higher is better."""
    if not results:
        return 0.0
    refusals = 0
    for result in results:
        if refused(result, threshold, key):
            refusals += 1
    return refusals / len(results)


def false_refusal_rate(results, threshold, key="scores"):
    """Of ANSWERABLE questions, the fraction wrongly refused. Lower is better."""
    if not results:
        return 0.0
    refusals = 0
    for result in results:
        if refused(result, threshold, key):
            refusals += 1
    return refusals / len(results)