"""Read side of the edition archive.

`build_history.py` fetches and diffs; this module answers the only two questions
a caller has:

    what was in force on date X?          -> in_force(X)
    what did article 126 say on date X?   -> article_as_of("126", X)

The archive is 41 consolidated editions folded into per-article versions, so a
lookup is a scan of one article's short timeline rather than a search through
41 copies of the code.

Loaded lazily: a missing archive must not stop the service from answering about
the edition it does have, and the file is only needed for historical questions.
"""

import json

from datetime import date
from pathlib import Path

HISTORY = Path(__file__).parent / "data" / "history.json"

_cache = None


def available():
    return HISTORY.exists()


def load(path=None):
    global _cache
    path = path or HISTORY
    if _cache is None or path != HISTORY:
        _cache = json.loads(path.read_text(encoding="utf-8"))
    return _cache


def editions(data=None):
    return (data or load())["editions"]


def in_force(on=None, data=None):
    """The edition that applies on `on` (ISO date, default today), or None."""
    on = on or date.today().isoformat()
    for edition in editions(data):
        if edition["valid_from"] <= on <= edition["valid_to"]:
            return edition
    return None


def article_as_of(article, on=None, data=None):
    """The version of one article in force on `on`, or None if it did not exist."""
    on = on or date.today().isoformat()
    for version in (data or load())["articles"].get(str(article), []):
        if version["from"] <= on <= version["to"]:
            return version
    return None


def coverage(data=None):
    """The window the archive spans, for a tool to state what it can answer."""
    items = editions(data)
    return {"from": items[0]["valid_from"], "to": items[-1]["valid_to"],
            "editions": len(items)}
