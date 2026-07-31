from pathlib import Path

from app.rag.embedding.base import EmbeddingProvider


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        model_name: str,
        version: str,
        dimension: int,
        batch_size: int,
        device: str,
        dtype: str,
        cache_folder: str | None,
        local_files_only: bool,
    ) -> None:
        self.model_name = model_name
        self.version = version
        self.dimension = dimension
        self.batch_size = batch_size
        self.device = device
        self.dtype = dtype
        self.cache_folder = str(Path(cache_folder).resolve()) if cache_folder else None
        self.local_files_only = local_files_only
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
            import torch
        except ImportError as exc:
            raise RuntimeError("Install the ai-service 'huggingface' extra") from exc
        if self.device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError(
                "EMBEDDING_DEVICE is CUDA but PyTorch cannot access an NVIDIA GPU"
            )
        torch_dtype = getattr(torch, self.dtype, None)
        if torch_dtype is None:
            raise ValueError(f"Unsupported embedding dtype: {self.dtype}")
        self._model = SentenceTransformer(
            self.model_name,
            device=self.device,
            cache_folder=self.cache_folder,
            local_files_only=self.local_files_only,
            model_kwargs={"torch_dtype": torch_dtype},
        )
        dimension_getter = getattr(self._model, "get_embedding_dimension", None)
        actual_dimension = (
            dimension_getter()
            if dimension_getter is not None
            else self._model.get_sentence_embedding_dimension()
        )
        if actual_dimension != self.dimension:
            raise RuntimeError(
                f"Embedding model returned {actual_dimension} dimensions; expected {self.dimension}"
            )
        return self._model

    @property
    def max_input_tokens(self) -> int:
        return int(getattr(self._load(), "max_seq_length", 8192))

    def count_tokens(self, text: str) -> int:
        encoded = self._load().tokenizer(text, add_special_tokens=True, truncation=False)
        return len(encoded["input_ids"])

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return vectors.tolist()
