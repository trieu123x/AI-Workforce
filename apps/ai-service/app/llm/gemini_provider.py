import httpx

from app.llm.base import LLMProvider, LLMResult


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, default_model: str = "gemini-2.0-flash") -> None:
        self.api_key = api_key
        self.default_model = default_model

    def generate(self, messages: list[dict[str, str]], *, model: str | None = None) -> LLMResult:
        selected = model or self.default_model
        contents = [
            {"role": "model" if item["role"] == "assistant" else "user", "parts": [{"text": item["content"]}]}
            for item in messages
            if item["role"] != "system"
        ]
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{selected}:generateContent",
            params={"key": self.api_key},
            json={"contents": contents},
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        usage = payload.get("usageMetadata", {})
        return LLMResult(
            content=payload["candidates"][0]["content"]["parts"][0]["text"],
            model=selected,
            provider=self.name,
            usage={
                "prompt_tokens": int(usage.get("promptTokenCount", 0)),
                "completion_tokens": int(usage.get("candidatesTokenCount", 0)),
                "cached_prompt_tokens": int(usage.get("cachedContentTokenCount", 0)),
            },
        )
