import threading
from typing import Any

from app.config import settings
from app.rag.reranking.base import BaseReranker


class BGEReranker(BaseReranker):
    """Lazy local CrossEncoder wrapper for BGE Reranker models (e.g. BAAI/bge-reranker-v2-m3, BAAI/bge-reranker-large)."""

    backend = "bge"

    def __init__(self) -> None:
        self.model_name = settings.RERANK_MODEL_NAME
        self._model: Any | None = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import CrossEncoder
                import torch
            except ImportError as exc:
                raise RuntimeError(
                    "Install the ai-service huggingface dependencies to use BGE reranking"
                ) from exc
            if settings.RERANK_DEVICE.startswith("cuda") and not torch.cuda.is_available():
                raise RuntimeError(
                    "RERANK_DEVICE is CUDA but PyTorch cannot access an NVIDIA GPU"
                )
            torch_dtype = getattr(torch, settings.RERANK_DTYPE, None)
            if torch_dtype is None:
                raise ValueError(f"Unsupported rerank dtype: {settings.RERANK_DTYPE}")

            self._model = CrossEncoder(
                self.model_name,
                device=settings.RERANK_DEVICE,
                cache_folder=settings.RERANK_CACHE_FOLDER or settings.EMBEDDING_CACHE_FOLDER,
                local_files_only=settings.RERANK_LOCAL_FILES_ONLY,
                max_length=settings.RERANK_MAX_LENGTH,
                model_kwargs={"torch_dtype": torch_dtype},
            )
        return self._model

    def score(
        self,
        query: str,
        documents: list[str],
        candidates: list[dict[str, Any]],
    ) -> list[float]:
        if not documents:
            return []
        try:
            from torch.nn import Sigmoid
        except ImportError as exc:
            raise RuntimeError("PyTorch is required to run BGE reranking") from exc

        model = self._load_model()
        pairs = [(query, document) for document in documents]
        batch_size = settings.RERANK_BATCH_SIZE
        with self._inference_lock:
            while True:
                try:
                    raw_scores = model.predict(
                        pairs,
                        batch_size=batch_size,
                        show_progress_bar=False,
                        activation_fn=Sigmoid(),
                        convert_to_numpy=True,
                    )
                    break
                except RuntimeError as exc:
                    is_cuda_oom = "out of memory" in str(exc).lower() and settings.RERANK_DEVICE.startswith("cuda")
                    if not is_cuda_oom or batch_size == 1:
                        raise
                    import torch

                    torch.cuda.empty_cache()
                    batch_size = max(1, batch_size // 2)
        return [max(0.0, min(1.0, float(score))) for score in raw_scores]
