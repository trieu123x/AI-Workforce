from fastapi import Depends, FastAPI, Header, HTTPException, status

from app.agents.base.registry import agent_registry
from app.config import settings
from app.llm.router import LLMRouter
from app.rag.embedding.factory import get_embedding_provider
from app.rag.ingestion.chunker import chunk_document
from app.rag.reranking.reranker import rerank_with_metadata
from app.shared.contracts import (
    AgentRouteRequest,
    AgentRouteResponse,
    ChunkRequest,
    ChunkResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    LLMGenerateRequest,
    LLMGenerateResponse,
    RerankRequest,
    RerankResponse,
    TokenCountRequest,
    TokenCountResponse,
)


app = FastAPI(
    title="AI Workforce AI Service",
    version="1.0.0",
    description="Stateless agent, RAG, embedding and prompt runtime.",
)


def require_internal_token(
    x_ai_service_key: str | None = Header(default=None),
) -> None:
    expected = settings.AI_SERVICE_INTERNAL_TOKEN
    if expected and x_ai_service_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid AI service credential",
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "ai-service", "version": "1.0.0"}


@app.get("/health/accelerator", dependencies=[Depends(require_internal_token)])
def accelerator_health() -> dict[str, object]:
    try:
        import torch
    except ImportError:
        return {"cuda_available": False, "reason": "PyTorch is not installed"}
    available = torch.cuda.is_available()
    return {
        "cuda_available": available,
        "torch_version": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "device_count": torch.cuda.device_count(),
        "device_name": torch.cuda.get_device_name(0) if available else None,
        "embedding_device": settings.EMBEDDING_DEVICE,
        "rerank_device": settings.RERANK_DEVICE,
    }


@app.post("/v1/rag/chunk", response_model=ChunkResponse, dependencies=[Depends(require_internal_token)])
def chunk_text(request: ChunkRequest) -> ChunkResponse:
    return ChunkResponse(chunks=chunk_document(
        request.content,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
    ))


@app.post("/v1/embeddings", response_model=EmbeddingResponse, dependencies=[Depends(require_internal_token)])
def create_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    provider = get_embedding_provider()
    texts = request.texts
    if request.input_type == "query":
        texts = [provider.prepare_query(text) for text in texts]
    vectors = provider.embed(texts)
    return EmbeddingResponse(
        vectors=vectors,
        token_counts=[provider.count_tokens(text) for text in texts],
        model=provider.model_name,
        version=provider.version,
        dimension=provider.dimension,
        max_input_tokens=provider.max_input_tokens,
    )


@app.post("/v1/token-count", response_model=TokenCountResponse, dependencies=[Depends(require_internal_token)])
def count_tokens(request: TokenCountRequest) -> TokenCountResponse:
    provider = get_embedding_provider()
    return TokenCountResponse(
        token_counts=[provider.count_tokens(text) for text in request.texts],
        max_input_tokens=provider.max_input_tokens,
    )


@app.post("/v1/rag/rerank", response_model=RerankResponse, dependencies=[Depends(require_internal_token)])
def rerank(request: RerankRequest) -> RerankResponse:
    outcome = rerank_with_metadata(
        request.query,
        request.candidates,
        top_k=request.top_k,
    )
    return RerankResponse(
        results=outcome.results,
        backend=outcome.backend,
        model=outcome.model,
        fallback_used=outcome.fallback_used,
        candidates_scored=outcome.candidates_scored,
        latency_ms=outcome.latency_ms,
    )


@app.post("/v1/agents/route", response_model=AgentRouteResponse, dependencies=[Depends(require_internal_token)])
def route_agent(request: AgentRouteRequest) -> AgentRouteResponse:
    agent = agent_registry.resolve(request.requested_role, request.message)
    return AgentRouteResponse(
        role=agent.role,
        agent_name=agent.name,
        capabilities=list(agent.capabilities),
    )


@app.post("/v1/llm/generate", response_model=LLMGenerateResponse, dependencies=[Depends(require_internal_token)])
def generate_text(request: LLMGenerateRequest) -> LLMGenerateResponse:
    provider = LLMRouter().provider(request.provider)
    result = provider.generate(request.messages, model=request.model)
    return LLMGenerateResponse(
        content=result.content,
        provider=result.provider,
        model=result.model,
        usage=result.usage,
    )
