"""HTTP client for the standalone, stateless AI runtime."""

from functools import lru_cache
from typing import Any

import httpx

from app.core.config import settings


class AIServiceError(RuntimeError):
    pass


class AIServiceClient:
    def __init__(self) -> None:
        self.base_url = (settings.AI_SERVICE_URL or "").rstrip("/")
        self.timeout = settings.AI_SERVICE_TIMEOUT_SECONDS

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    @property
    def headers(self) -> dict[str, str]:
        if not settings.AI_SERVICE_INTERNAL_TOKEN:
            return {}
        return {"X-AI-Service-Key": settings.AI_SERVICE_INTERNAL_TOKEN}

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise AIServiceError("AI service URL is not configured")
        try:
            response = httpx.post(
                f"{self.base_url}{path}",
                json=payload,
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise AIServiceError(f"AI service request failed: {path}") from exc

    def chunk_document(
        self,
        content: str,
        *,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[dict[str, Any]]:
        result = self._post("/v1/rag/chunk", {
            "content": content,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        })
        return list(result["chunks"])

    def embed(self, texts: list[str], *, input_type: str = "document") -> dict[str, Any]:
        return self._post("/v1/embeddings", {"texts": texts, "input_type": input_type})

    def count_tokens(self, texts: list[str]) -> dict[str, Any]:
        return self._post("/v1/token-count", {"texts": texts})

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        result = self._post("/v1/rag/rerank", {
            "query": query,
            "candidates": candidates,
            "top_k": top_k,
        })
        return list(result["results"])


@lru_cache(maxsize=1)
def get_ai_service_client() -> AIServiceClient:
    return AIServiceClient()
