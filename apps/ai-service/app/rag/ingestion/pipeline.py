from typing import Any

from app.rag.ingestion.chunker import chunk_document
from app.rag.ingestion.parser import parse_document


def parse_and_chunk(filename: str, data: bytes) -> list[dict[str, Any]]:
    text = parse_document(filename, data).strip()
    if not text:
        raise ValueError("No readable text found in the file")
    return chunk_document(text)
