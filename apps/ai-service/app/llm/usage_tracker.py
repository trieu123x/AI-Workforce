from dataclasses import dataclass


@dataclass
class UsageTracker:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_prompt_tokens: int = 0

    def add(self, usage: dict[str, int]) -> None:
        self.prompt_tokens += int(usage.get("prompt_tokens", 0))
        self.completion_tokens += int(usage.get("completion_tokens", 0))
        self.cached_prompt_tokens += int(usage.get("cached_prompt_tokens", 0))

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens
