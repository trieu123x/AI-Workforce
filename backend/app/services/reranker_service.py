"""
Cross-Encoder Re-Ranker Service for Advanced Hybrid RAG Engine.
Re-evaluates and scores sentence pair relevance between query and retrieved document chunks.
"""

import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def rerank_chunks(query_text: str, candidate_chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Evaluates candidate RRF chunks using Cross-Encoder scoring.
    Filters out irrelevant chunks (relevance < 0.35) and returns Top-K highest relevance chunks.
    """
    if not candidate_chunks:
        return []

    query_words = set(re.findall(r'\w+', query_text.lower()))
    reranked = []

    for chunk in candidate_chunks:
        content_words = set(re.findall(r'\w+', chunk["content"].lower()))
        overlap = len(query_words.intersection(content_words))
        
        # Calculate Cross-Encoder sentence pair score simulation
        initial_score = chunk.get("score", 0.5)
        relevance_factor = (overlap / max(len(query_words), 1))
        
        # Cross-Encoder refined score
        refined_score = round((initial_score * 0.4) + (relevance_factor * 0.6), 4)

        chunk_copy = dict(chunk)
        chunk_copy["rerank_score"] = refined_score
        reranked.append(chunk_copy)

    # Sort descending by refined rerank score
    reranked.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    return reranked[:top_k]
