from typing import Any


def build_citation(chunk: dict[str, Any]) -> str:
    source = chunk.get("source_file") or chunk.get("document_name") or "unknown"
    section = chunk.get("section_title") or "Mở đầu"
    page = chunk.get("page_start") or chunk.get("page")
    page_part = f", trang {page}" if page else ""
    return f"[Nguồn: {source}, {section}{page_part}]"
