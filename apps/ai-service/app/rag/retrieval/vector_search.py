import math
from typing import Any


def cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def vector_search(query_vector: list[float], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = [
        {**candidate, "_dense_score": cosine_similarity(query_vector, candidate["embedding"])}
        for candidate in candidates
        if candidate.get("embedding")
    ]
    return sorted(ranked, key=lambda item: item["_dense_score"], reverse=True)
