from typing import Protocol


class DocumentLoader(Protocol):
    def __call__(self, data: bytes) -> str: ...
