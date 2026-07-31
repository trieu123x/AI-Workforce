from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    AI_SERVICE_HOST: str = "0.0.0.0"
    AI_SERVICE_PORT: int = 8100
    AI_SERVICE_INTERNAL_TOKEN: Optional[str] = None

    EMBEDDING_BACKEND: str = "deterministic"
    EMBEDDING_MODEL_NAME: str = "Qwen/Qwen3-Embedding-0.6B"
    EMBEDDING_VERSION: str = "qwen3-embedding-v1"
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_BATCH_SIZE: int = 16
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_DTYPE: str = "float32"
    EMBEDDING_CACHE_FOLDER: Optional[str] = None
    EMBEDDING_LOCAL_FILES_ONLY: bool = False
    EMBEDDING_MAX_RETRIES: int = 3

    RAG_CHUNK_TARGET_TOKENS: int = 450
    RAG_CHUNK_MAX_TOKENS: int = 700
    RAG_CHUNK_OVERLAP_TOKENS: int = 80
    RAG_MIN_DENSE_SCORE: float = 0.50
    RAG_MIN_RELEVANCE_SCORE: float = 0.50

    RERANK_BACKEND: str = "bge"
    RERANK_MODEL_NAME: str = "BAAI/bge-reranker-v2-m3"
    RERANK_DEVICE: str = "cpu"
    RERANK_DTYPE: str = "float32"
    RERANK_CACHE_FOLDER: Optional[str] = None
    RERANK_LOCAL_FILES_ONLY: bool = False
    RERANK_BATCH_SIZE: int = Field(default=4, ge=1, le=128)
    RERANK_MAX_LENGTH: int = Field(default=4096, ge=128, le=32768)
    RERANK_CANDIDATE_LIMIT: int = Field(default=30, ge=1, le=200)
    RERANK_MIN_MODEL_SCORE: float = Field(default=0.15, ge=0.0, le=1.0)
    RERANK_MODEL_WEIGHT: float = Field(default=0.90, ge=0.0, le=1.0)
    RERANK_FALLBACK_ENABLED: bool = True
    RERANK_INSTRUCTION: str = (
        "Truy xuất đoạn tài liệu nội bộ chính xác và đủ căn cứ để trả lời câu hỏi."
    )

    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_AI_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
