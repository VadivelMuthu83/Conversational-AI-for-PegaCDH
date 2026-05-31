"""
Vector store: FAISS + BM25 hybrid search with persistence.
Uses settings.index_dir (resolves RAG_STORE_PATH or INDEX_DIR).
"""
import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from app.core.config import settings
from app.rag.chunker import Chunk
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider

logger = logging.getLogger(__name__)


class SearchResult:
    def __init__(self, chunk: Chunk, score: float, search_type: str = "hybrid"):
        self.chunk = chunk
        self.score = score
        self.search_type = search_type


class VectorStore:
    INDEX_FILE  = "faiss.index"
    CHUNKS_FILE = "chunks.pkl"
    BM25_FILE   = "bm25.pkl"

    def __init__(self):
        self._chunks: List[Chunk] = []
        self._faiss_index = None
        self._bm25 = None
        self._embedder: Optional[EmbeddingProvider] = None
        # Use resolved property — handles RAG_STORE_PATH or INDEX_DIR
        self._index_dir = Path(settings.index_dir)
        self._index_dir.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        self._embedder = get_embedding_provider()
        if settings.INDEX_PERSIST:
            await self._try_load()

    async def build(self, chunks: List[Chunk]):
        self._chunks = chunks
        if not chunks:
            logger.warning("VectorStore.build: 0 chunks — index will be empty")
            return
        logger.info(f"Building index for {len(chunks)} chunks …")
        await self._build_bm25(chunks)
        texts = [c.text for c in chunks]
        embs = await self._embedder.embed(texts)
        await self._build_faiss(embs)
        if settings.INDEX_PERSIST:
            self._save()
        logger.info(f"Index built: {len(chunks)} vectors, dim={self._embedder.dimension()}")

    async def search(
        self,
        query: str,
        top_k: int = None,
        mode: str = None,
        filter_files: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        k = top_k or settings.TOP_K_RETRIEVAL
        m = mode or settings.RETRIEVAL_MODE
        if not self._chunks:
            return []
        if m == "semantic":
            results = await self._semantic_search(query, k * 2)
        elif m == "bm25":
            results = self._bm25_search(query, k * 2)
        else:
            results = await self._hybrid_search(query, k)
        if filter_files:
            results = [r for r in results if r.chunk.file_name in filter_files]
        return results

    async def _semantic_search(self, query: str, k: int) -> List[SearchResult]:
        if self._faiss_index is None:
            return self._bm25_search(query, k)
        q_emb = await self._embedder.embed([query])
        k_actual = min(k, len(self._chunks))
        scores, indices = self._faiss_index.search(q_emb, k_actual)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if 0 <= idx < len(self._chunks):
                results.append(SearchResult(
                    chunk=self._chunks[idx], score=float(score), search_type="semantic"
                ))
        return results

    def _bm25_search(self, query: str, k: int) -> List[SearchResult]:
        if self._bm25 is None:
            return self._fallback_keyword_search(query, k)
        tokens = query.lower().split()
        scores = self._bm25.get_scores(tokens)
        top_idx = np.argsort(scores)[::-1][:k]
        return [
            SearchResult(chunk=self._chunks[i], score=float(scores[i]), search_type="bm25")
            for i in top_idx if scores[i] > 0 and i < len(self._chunks)
        ]

    async def _hybrid_search(self, query: str, k: int) -> List[SearchResult]:
        alpha = settings.HYBRID_ALPHA
        fetch_k = k * 3
        semantic_results = await self._semantic_search(query, fetch_k)
        bm25_results = self._bm25_search(query, fetch_k)
        rrf_k = 60
        scores: Dict[str, float] = {}
        chunk_map: Dict[str, Chunk] = {}
        for rank, r in enumerate(semantic_results):
            cid = r.chunk.id
            scores[cid] = scores.get(cid, 0) + alpha / (rank + rrf_k)
            chunk_map[cid] = r.chunk
        for rank, r in enumerate(bm25_results):
            cid = r.chunk.id
            scores[cid] = scores.get(cid, 0) + (1 - alpha) / (rank + rrf_k)
            chunk_map[cid] = r.chunk
        sorted_ids = sorted(scores, key=scores.get, reverse=True)[:k]
        return [
            SearchResult(chunk=chunk_map[cid], score=scores[cid], search_type="hybrid")
            for cid in sorted_ids
        ]

    def _fallback_keyword_search(self, query: str, k: int) -> List[SearchResult]:
        terms = set(query.lower().split())
        scored = []
        for chunk in self._chunks:
            score = sum(1 for t in terms if t in chunk.text.lower())
            if score > 0:
                scored.append(SearchResult(chunk=chunk, score=float(score), search_type="keyword"))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]

    async def _build_bm25(self, chunks: List[Chunk]):
        try:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi([c.text.lower().split() for c in chunks])
            logger.info("BM25 index built")
        except ImportError:
            logger.warning("rank-bm25 not installed — BM25 disabled")

    async def _build_faiss(self, embs: np.ndarray):
        try:
            import faiss
            dim = embs.shape[1]
            index = faiss.IndexFlatIP(dim)
            index.add(embs)
            self._faiss_index = index
            logger.info(f"FAISS IndexFlatIP built: {index.ntotal} vectors (dim={dim})")
        except ImportError:
            logger.warning("faiss-cpu not installed — semantic search disabled")

    def _save(self):
        try:
            import faiss
            if self._faiss_index:
                faiss.write_index(
                    self._faiss_index,
                    str(self._index_dir / self.INDEX_FILE),
                )
            with open(self._index_dir / self.CHUNKS_FILE, "wb") as f:
                pickle.dump(self._chunks, f)
            if self._bm25:
                with open(self._index_dir / self.BM25_FILE, "wb") as f:
                    pickle.dump(self._bm25, f)
            logger.info(f"Index saved to {self._index_dir}")
        except Exception as e:
            logger.error(f"Failed to save index: {e}")

    async def _try_load(self):
        chunks_path = self._index_dir / self.CHUNKS_FILE
        if not chunks_path.exists():
            return
        try:
            with open(chunks_path, "rb") as f:
                self._chunks = pickle.load(f)
            index_path = self._index_dir / self.INDEX_FILE
            if index_path.exists():
                import faiss
                self._faiss_index = faiss.read_index(str(index_path))
                logger.info(f"FAISS index loaded: {self._faiss_index.ntotal} vectors")
            bm25_path = self._index_dir / self.BM25_FILE
            if bm25_path.exists():
                with open(bm25_path, "rb") as f:
                    self._bm25 = pickle.load(f)
            logger.info(f"Persisted index restored: {len(self._chunks)} chunks")
        except Exception as e:
            logger.warning(f"Could not load persisted index: {e}")

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def get_chunks(self) -> List[Chunk]:
        return self._chunks

    def get_unique_files(self) -> List[str]:
        return list({c.file_name for c in self._chunks})
