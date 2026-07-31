from dataclasses import dataclass


@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    category: str
    requires_approval: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDescriptor] = {}

    def register(self, tool: ToolDescriptor) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDescriptor:
        return self._tools[name]
