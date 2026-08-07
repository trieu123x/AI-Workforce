"""Schema-driven legal document drafting primitives."""

from app.services.legal_documents.schemas import (
    DOCUMENT_SCHEMAS,
    get_document_schema,
    list_document_schemas,
)
from app.services.legal_documents.validators import validate_document_fields

__all__ = [
    "DOCUMENT_SCHEMAS",
    "get_document_schema",
    "list_document_schemas",
    "validate_document_fields",
]
