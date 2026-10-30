"""Is the loaded corpus still the law in force?

A RAG system over a consolidated edition has a failure mode that has nothing to
do with retrieval: the edition expires, the text does not change, and every
answer quietly becomes a statement about superseded law. Nothing in the answer
looks wrong, because the retrieved article is the article that was loaded.

So the expiry is computed, not assumed, and it is surfaced. `main.py` reports it
on /health and the interface shows a banner; the retrieval path is untouched,
because "this is the old edition" is information for the reader, not a reason to
refuse a question.

Pure functions over an ISO date string, so this is testable without loading the
corpus or mocking a clock.
"""

from datetime import date


def is_expired(edition_to, on=None):
    """True when today is past the last day the edition was in force."""
    return (on or date.today()) > date.fromisoformat(edition_to)


def days_left(edition_to, on=None):
    """Whole days until the edition stops being current; negative once expired."""
    return (date.fromisoformat(edition_to) - (on or date.today())).days


def warning(edition_to, on=None):
    """One sentence for a log or a tool result, or None while the edition holds."""
    if not is_expired(edition_to, on):
        return None
    return (
        f"corpus edition expired on {edition_to}; answers describe the law as of "
        "that date, not as it stands today"
    )
