
THRESHOLD = 0.5


def should_answer(results):
    """True if the best retrieved article clears the confidence threshold."""
    if not results:
        return False
    return results[0]["score"] >= THRESHOLD