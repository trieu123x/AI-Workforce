from typing import Any

from app.rag.retrieval.keyword_search import keyword_search
from app.rag.retrieval.vector_search import vector_search
from app.rag.reranking.score_fusion import reciprocal_rank_fusion


def hybrid_search(
    query: str,
    query_vector: list[float],
    candidates: list[dict[str, Any]],
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    dense = vector_search(query_vector, candidates)[:limit]
    sparse = keyword_search(query, candidates)[:limit]
    return reciprocal_rank_fusion(dense, sparse)[:limit]
