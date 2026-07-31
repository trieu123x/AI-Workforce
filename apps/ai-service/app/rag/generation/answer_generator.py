from app.rag.generation.citation_builder import build_citation


def grounded_excerpt_answer(chunks: list[dict]) -> str:
    if not chunks:
        return "Không tìm thấy tài liệu phù hợp để trả lời."
    best = chunks[0]
    return f"{best.get('content', '')}\n\n{build_citation(best)}"
