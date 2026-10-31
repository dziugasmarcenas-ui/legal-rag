"""Check that an answer only cites provisions that were actually retrieved.

The citations in a response are attached by the retriever, not written by the
model. But the model still writes phrases like "pagal Darbo kodekso 59
straipsnį" in prose, and nothing has been checking whether that number came from
the retrieved set or from the model's own memory.

This module does that check. It does not rewrite or suppress the answer: it
reports which cited articles the retriever did not supply, so the caller (and
the logs) can see a hallucinated reference for what it is.

    >>> verify("Pagal 59 straipsnį...", results)
    {'cited': ['59'], 'supported': ['59'], 'unsupported': []}
"""

import re

# "59 straipsnis", "59 straipsnio", "59 str.", "72-1 straipsnį"
REFERENCE = re.compile(r"(\d{1,3}(?:-\d{1,2})?)\s*(?:straipsn\w*|str\.)", re.IGNORECASE)


def verify(answer, results):
    """Return the articles the answer names and which of them were not retrieved."""
    if not answer:
        return {"cited": [], "supported": [], "unsupported": []}

    served = {str(r["article"]) for r in results if r.get("article")}
    cited = []
    for match in REFERENCE.finditer(answer):
        identifier = match.group(1)
        if identifier not in cited:
            cited.append(identifier)

    supported = sorted(i for i in cited if i in served)
    unsupported = sorted(i for i in cited if i not in served)
    return {"cited": sorted(cited), "supported": supported, "unsupported": unsupported}
