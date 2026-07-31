import re
from typing import Any


def keyword_search(query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = set(re.findall(r"\w+", query.lower()))
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        words = set(re.findall(r"\w+", str(candidate.get("content", "")).lower()))
        score = len(terms.intersection(words)) / max(len(terms), 1)
        if score:
            ranked.append({**candidate, "_sparse_score": score})
    return sorted(ranked, key=lambda item: item["_sparse_score"], reverse=True)
