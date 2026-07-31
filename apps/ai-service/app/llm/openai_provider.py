import httpx

from app.llm.base import LLMProvider, LLMResult


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, default_model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.default_model = default_model

    def generate(self, messages: list[dict[str, str]], *, model: str | None = None) -> LLMResult:
        selected = model or self.default_model
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": selected, "messages": messages},
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        usage = payload.get("usage", {})
        return LLMResult(
            content=payload["choices"][0]["message"]["content"],
            model=payload.get("model", selected),
            provider=self.name,
            usage={
                "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                "completion_tokens": int(usage.get("completion_tokens", 0)),
                "cached_prompt_tokens": int(usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)),
            },
        )
