"""Independent, explainable contract-review module."""

from app.services.contract_review.analyzer import review_contract
from app.services.contract_review.clause_parser import (
    detect_contract_type,
    extract_review_metadata,
    split_contract_clauses,
)

__all__ = [
    "detect_contract_type",
    "extract_review_metadata",
    "review_contract",
    "split_contract_clauses",
]
