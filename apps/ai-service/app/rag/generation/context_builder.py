from typing import Any


def build_context(chunks: list[dict[str, Any]], *, max_characters: int = 12000) -> str:
    blocks: list[str] = []
    used = 0
    for index, chunk in enumerate(chunks, start=1):
        block = f"[{index}] {chunk.get('document_title', chunk.get('document_name', 'Tài liệu'))}\n{chunk.get('content', '')}"
        if used + len(block) > max_characters:
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)
