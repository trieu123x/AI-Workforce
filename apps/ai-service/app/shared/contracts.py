from typing import Any, Literal

from pydantic import BaseModel, Field


class ChunkRequest(BaseModel):
    content: str = Field(min_length=1)
    chunk_size: int | None = Field(default=None, ge=1)
    chunk_overlap: int | None = Field(default=None, ge=0)


class ChunkResponse(BaseModel):
    chunks: list[dict[str, Any]]


class EmbeddingRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=128)
    input_type: Literal["document", "query"] = "document"


class EmbeddingResponse(BaseModel):
    vectors: list[list[float]]
    token_counts: list[int]
    model: str
    version: str
    dimension: int
    max_input_tokens: int


class TokenCountRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=128)


class TokenCountResponse(BaseModel):
    token_counts: list[int]
    max_input_tokens: int


class RerankRequest(BaseModel):
    query: str = Field(min_length=1)
    candidates: list[dict[str, Any]]
    top_k: int = Field(default=5, ge=1, le=100)


class RerankResponse(BaseModel):
    results: list[dict[str, Any]]
    backend: str
    model: str
    fallback_used: bool
    candidates_scored: int
    latency_ms: float


class AgentRouteRequest(BaseModel):
    requested_role: str | None = None
    message: str = Field(min_length=1)


class AgentRouteResponse(BaseModel):
    role: str
    agent_name: str
    capabilities: list[str]


class LLMGenerateRequest(BaseModel):
    messages: list[dict[str, str]] = Field(min_length=1, max_length=100)
    provider: str | None = None
    model: str | None = None


class LLMGenerateResponse(BaseModel):
    content: str
    provider: str
    model: str
    usage: dict[str, int]
