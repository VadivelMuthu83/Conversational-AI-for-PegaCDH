"""
Reranker: improves retrieval quality by rescoring top-K candidates.
Supports:
  - CrossEncoder (local, sentence-transformers) — good quality, no API cost
  - Cohere Rerank API                           — best quality, API cost
Falls back gracefully if neither is available.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List

from app.core.config import settings
from app.rag.vector_store import SearchResult

logger = logging.getLogger(__name__)


class Reranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, results: List[SearchResult],
                     top_k: int) -> List[SearchResult]:
        pass


# ─── CrossEncoder (local) ─────────────────────────────────────────────────────

class CrossEncoderReranker(Reranker):
    """
    Uses a bi-encoder CrossEncoder model locally.
    Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (~85MB, fast on CPU)
    """

    def __init__(self, model_name: str = None):
        self._model_name = model_name or settings.RERANKER_MODEL
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading CrossEncoder: {self._model_name}")
            self._model = CrossEncoder(self._model_name)

    async def rerank(self, query: str, results: List[SearchResult],
                     top_k: int) -> List[SearchResult]:
        if not results:
            return results

        loop = asyncio.get_event_loop()

        def _score():
            self._load()
            pairs = [(query, r.chunk.text) for r in results]
            scores = self._model.predict(pairs)
            return scores

        scores = await loop.run_in_executor(None, _score)

        for result, score in zip(results, scores):
            result.score = float(score)
            result.search_type = "reranked_cross_encoder"

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]


# ─── Cohere Rerank ────────────────────────────────────────────────────────────

class CohereReranker(Reranker):
    """
    Uses Cohere's Rerank API — best-in-class retrieval quality.
    Requires COHERE_API_KEY.
    """

    def __init__(self):
        import cohere
        self._client = cohere.AsyncClient(api_key=settings.COHERE_API_KEY)

    async def rerank(self, query: str, results: List[SearchResult],
                     top_k: int) -> List[SearchResult]:
        if not results:
            return results

        docs = [r.chunk.text for r in results]
        resp = await self._client.rerank(
            model="rerank-multilingual-v3.0",
            query=query,
            documents=docs,
            top_n=top_k,
        )

        reranked = []
        for hit in resp.results:
            r = results[hit.index]
            r.score = hit.relevance_score
            r.search_type = "reranked_cohere"
            reranked.append(r)
        return reranked


# ─── Passthrough (no reranking) ───────────────────────────────────────────────

class PassthroughReranker(Reranker):
    async def rerank(self, query: str, results: List[SearchResult],
                     top_k: int) -> List[SearchResult]:
        return results[:top_k]


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_reranker() -> Reranker:
    if not settings.RERANKER_ENABLED:
        return PassthroughReranker()

    provider = settings.RERANKER_PROVIDER.lower()
    try:
        if provider == "cohere":
            if not settings.COHERE_API_KEY:
                logger.warning("COHERE_API_KEY not set; using CrossEncoder")
                return CrossEncoderReranker()
            return CohereReranker()
        else:
            return CrossEncoderReranker()
    except Exception as e:
        logger.warning(f"Reranker init failed ({e}); using passthrough")
        return PassthroughReranker()
