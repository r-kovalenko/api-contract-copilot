"""Deterministic reciprocal-rank fusion over bounded source candidate lists."""

from fractions import Fraction

CANDIDATE_LIMIT = 50
RRF_K = 60


def fuse(keyword, vector):
    scores = {}
    evidence = {}
    for rows in (keyword, vector):
        seen = set()
        for chunk, document, _ in rows[:CANDIDATE_LIMIT]:
            if chunk.id in seen:
                continue
            seen.add(chunk.id)
            scores[chunk.id] = scores.get(chunk.id, Fraction()) + Fraction(1, RRF_K + len(seen))
            evidence.setdefault(chunk.id, (chunk, document))
    ordered = sorted(scores, key=lambda key: (-scores[key], key))
    return [(*evidence[key], float(scores[key])) for key in ordered]
