from collections import deque


class ShortTermMemory:
    def __init__(self, max_items: int = 20) -> None:
        self._items: deque[dict] = deque(maxlen=max_items)

    def add(self, item: dict) -> None:
        self._items.append(item)

    def items(self) -> list[dict]:
        return list(self._items)
