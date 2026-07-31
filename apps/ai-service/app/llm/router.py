from app.config import settings
from app.llm.base import LLMProvider
from app.llm.gemini_provider import GeminiProvider
from app.llm.local_provider import LocalProvider
from app.llm.openai_provider import OpenAIProvider


class LLMRouter:
    def provider(self, name: str | None = None) -> LLMProvider:
        selected = (name or "").lower()
        if selected == "openai" or (not selected and settings.OPENAI_API_KEY):
            if not settings.OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY is not configured")
            return OpenAIProvider(settings.OPENAI_API_KEY)
        if selected == "gemini" or (not selected and settings.GOOGLE_AI_API_KEY):
            if not settings.GOOGLE_AI_API_KEY:
                raise RuntimeError("GOOGLE_AI_API_KEY is not configured")
            return GeminiProvider(settings.GOOGLE_AI_API_KEY)
        return LocalProvider()
