"""A lexical retriever, because meaning and words fail differently.

The vector index answers "what is this about"; it does not reliably answer "which
article says 126" or "the user typed atostogu without the ogonek". Lithuanian
makes that second failure common: `atostogų` and `atostogu` are the same word to
a person and different tokens to a keyword index, and Voyage is good but not
guaranteed to bridge a misspelling.

This is BM25 over the same article text, with diacritics folded so both spellings
match. It is a few dozen lines and no dependency; the honest reason to add it is
that it is a different failure mode, not that it is fashionable.

Fusion is Reciprocal Rank Fusion: it needs only ranks, so two scores on
incomparable scales never have to be normalised against each other.
"""

import math
import re
import unicodedata

from collections import Counter

import retrieval

TOKEN = re.compile(r"[0-9a-ząčęėįšųūž]+", re.IGNORECASE)

# BM25 defaults, unchanged from the literature: nothing here is tuned on the
# benchmark, because tuning a ranker on 30 questions is how you get a number
# that does not survive the 31st.
K1 = 1.5
B = 0.75
RRF_K = 60


def fold(text):
    """Fold diacritics: atostogų -> atostogu. Both spellings must match."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def tokenise(text):
    return TOKEN.findall(fold(text))


class Index:
    def __init__(self, articles):
        self.ids = [a["article"] for a in articles]
        self.docs = [
            tokenise(a["title"] + " " + a["text"]) for a in articles
        ]
        self.lengths = [len(d) for d in self.docs]
        self.average = sum(self.lengths) / max(len(self.lengths), 1)
        self.term_frequencies = [Counter(d) for d in self.docs]

        document_frequency = Counter()
        for doc in self.docs:
            document_frequency.update(set(doc))
        total = len(self.docs)
        self.idf = {
            term: math.log(1 + (total - df + 0.5) / (df + 0.5))
            for term, df in document_frequency.items()
        }

    def scores(self, query):
        terms = tokenise(query)
        if not terms:
            return [0.0] * len(self.docs)

        scores = []
        for frequencies, length in zip(self.term_frequencies, self.lengths):
            score = 0.0
            for term in terms:
                frequency = frequencies.get(term)
                if not frequency:
                    continue
                denominator = frequency + K1 * (
                    1 - B + B * length / max(self.average, 1e-9)
                )
                score += self.idf.get(term, 0.0) * frequency * (K1 + 1) / denominator
            scores.append(score)
        return scores

    def ranked(self, query):
        """Article ids, best first. Only documents with a real match are returned."""
        scores = self.scores(query)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self.ids[i] for i in order if scores[i] > 0]


def build(articles=None):
    return Index(articles if articles is not None else retrieval.ARTICLES)


def fuse(vector_ids, lexical_ids, k=RRF_K):
    """Merge two ranked lists by Reciprocal Rank Fusion, best first."""
    scores = {}
    for ranked in (vector_ids, lexical_ids):
        for rank, identifier in enumerate(ranked):
            scores[identifier] = scores.get(identifier, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda i: scores[i], reverse=True)
