from dataclasses import dataclass, field


@dataclass
class ConversationMemory:
    thread_id: str
    messages: list[dict[str, str]] = field(default_factory=list)

    def append(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
