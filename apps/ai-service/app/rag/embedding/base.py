from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    model_name: str
    version: str
    dimension: int
    batch_size: int

    @property
    def max_input_tokens(self) -> int:
        return 8192

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def prepare_query(self, question: str) -> str:
        return (
            "Truy xuất tài liệu nội bộ phù hợp để trả lời câu hỏi:\n"
            f"{question.strip()}"
        )
