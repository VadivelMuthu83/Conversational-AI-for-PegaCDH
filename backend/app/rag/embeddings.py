"""
Embedding service — local SentenceTransformer or OpenAI.
Compatible with sentence-transformers 3.x and openai 2.x.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: List[str]) -> np.ndarray: ...
    @abstractmethod
    def dimension(self) -> int: ...


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = None):
        self._model_name = model_name or settings.embedding_model_name
        self._model      = None
        self._dim        = 384

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SentenceTransformer: {self._model_name}")
            self._model = SentenceTransformer(self._model_name)
            self._dim   = self._model.get_sentence_embedding_dimension()
            logger.info(f"Embedding model ready — dim={self._dim}")

    def dimension(self) -> int:
        return self._dim

    async def embed(self, texts: List[str]) -> np.ndarray:
        loop = asyncio.get_event_loop()

        def _encode():
            self._load()
            bs   = settings.BATCH_EMBED_SIZE
            embs = []
            for i in range(0, len(texts), bs):
                embs.append(
                    self._model.encode(
                        texts[i:i + bs],
                        batch_size=bs,
                        show_progress_bar=False,
                        normalize_embeddings=True,
                    )
                )
            return np.vstack(embs).astype("float32")

        return await loop.run_in_executor(None, _encode)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        # openai v2.x — same AsyncOpenAI class
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._model  = settings.EMBEDDING_MODEL_OPENAI
        self._dim    = 1536 if "small" in self._model else 3072

    def dimension(self) -> int:
        return self._dim

    async def embed(self, texts: List[str]) -> np.ndarray:
        bs   = settings.BATCH_EMBED_SIZE
        embs = []
        for i in range(0, len(texts), bs):
            resp = await self._client.embeddings.create(
                input=texts[i:i + bs], model=self._model
            )
            embs.extend([e.embedding for e in resp.data])
        arr   = np.array(embs, dtype="float32")
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        arr  /= np.where(norms == 0, 1, norms)
        return arr


_provider_cache = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider_cache
    if _provider_cache is not None:
        return _provider_cache
    if settings.EMBEDDING_PROVIDER.lower() == "openai" and settings.OPENAI_API_KEY:
        logger.info("Using OpenAI embeddings")
        _provider_cache = OpenAIEmbeddingProvider()
    else:
        model = settings.embedding_model_name
        logger.info(f"Using local SentenceTransformer: {model}")
        _provider_cache = LocalEmbeddingProvider(model)
    return _provider_cache
