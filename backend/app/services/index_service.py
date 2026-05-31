"""
IndexService — compatibility shim over RAGPipeline.

The real work is done by app.rag.pipeline (RAGPipeline).
This class exists only so that older code paths that reference
app.state.index_service continue working without changes.

All three env var pairs are resolved here via settings properties:
  KNOWLEDGE_PATH  / LOCAL_FILES_PATH  → settings.files_path
  RAG_STORE_PATH  / INDEX_DIR         → settings.index_dir
  EMBEDDING_MODEL / EMBEDDING_MODEL_LOCAL → settings.embedding_model_name
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.parsers.file_parser import FileParser, ParsedFile
from app.services.file_source import get_file_source

logger = logging.getLogger(__name__)


class ChunkRecord:
    """Minimal chunk record used by legacy search paths."""
    def __init__(self, chunk_id: int, file_name: str, file_type: str,
                 text: str, metadata: Optional[Dict] = None):
        self.chunk_id = chunk_id
        self.file_name = file_name
        self.file_type = file_type
        self.text = text
        self.metadata = metadata or {}


class IndexService:
    """
    Legacy index service — now a thin wrapper that delegates to RAGPipeline.
    Kept for backward compatibility with health.py and files.py routes.

    Resolved paths at construction time:
      self.files_path  ← KNOWLEDGE_PATH or LOCAL_FILES_PATH
      self.index_dir   ← RAG_STORE_PATH  or INDEX_DIR
      self.embed_model ← EMBEDDING_MODEL or EMBEDDING_MODEL_LOCAL
    """

    def __init__(self):
        # ── Resolve all three env var pairs via config properties ─────────────
        self.files_path: str  = settings.files_path          # KNOWLEDGE_PATH fallback LOCAL_FILES_PATH
        self.index_dir: Path  = Path(settings.index_dir)     # RAG_STORE_PATH  fallback INDEX_DIR
        self.embed_model: str = settings.embedding_model_name  # EMBEDDING_MODEL  fallback EMBEDDING_MODEL_LOCAL

        logger.info(f"IndexService paths resolved:")
        logger.info(f"  files_path  → {self.files_path}  (KNOWLEDGE_PATH or LOCAL_FILES_PATH)")
        logger.info(f"  index_dir   → {self.index_dir}   (RAG_STORE_PATH or INDEX_DIR)")
        logger.info(f"  embed_model → {self.embed_model} (EMBEDDING_MODEL or EMBEDDING_MODEL_LOCAL)")

        self.parser = FileParser(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        self.chunks: List[ChunkRecord] = []
        self.parsed_files: List[ParsedFile] = []

        # Will be set by main.py after RAGPipeline is ready
        self._rag_pipeline = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def initialize(self):
        self.index_dir.mkdir(parents=True, exist_ok=True)
        logger.info("IndexService initialised (delegates to RAGPipeline)")

    async def refresh_index(self):
        """Delegate full re-index to the RAGPipeline if wired up."""
        if self._rag_pipeline is not None:
            stats = await self._rag_pipeline.index_all()
            # Sync local mirrors so health/files endpoints stay accurate
            self.parsed_files = self._rag_pipeline._parsed_files
            self.chunks = [
                ChunkRecord(
                    chunk_id=i,
                    file_name=c.file_name,
                    file_type=c.file_type,
                    text=c.text,
                    metadata=c.metadata,
                )
                for i, c in enumerate(self._rag_pipeline._vector_store.get_chunks())
            ]
            return stats
        # Fallback: basic parse without vector index (e.g. in tests)
        return await self._basic_index()

    async def _basic_index(self):
        """Parse files without building a vector index (test/fallback mode)."""
        source = get_file_source()
        file_list = source.list_files()
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        self.chunks = []
        self.parsed_files = []
        chunk_id = 0
        for fi in file_list:
            if not self.parser.can_parse(fi.name) or fi.size > max_bytes:
                continue
            try:
                content = source.read_file(fi.path)
                for pf in self.parser.parse_bytes(content, fi.name):
                    self.parsed_files.append(pf)
                    for text in pf.text_chunks:
                        self.chunks.append(ChunkRecord(
                            chunk_id=chunk_id,
                            file_name=pf.name,
                            file_type=pf.file_type,
                            text=text,
                            metadata={"row_count": pf.row_count, "columns": pf.columns},
                        ))
                        chunk_id += 1
            except Exception as e:
                logger.error(f"Error indexing {fi.name}: {e}")
        logger.info(f"Basic index: {len(self.parsed_files)} files, {len(self.chunks)} chunks")
        return {"files_parsed": len(self.parsed_files), "total_chunks": len(self.chunks)}

    # ── Search (delegates to RAGPipeline if available) ────────────────────────

    async def search(self, query: str, top_k: Optional[int] = None) -> List[ChunkRecord]:
        if self._rag_pipeline is not None:
            results = await self._rag_pipeline.retrieve(query, top_k=top_k)
            return [
                ChunkRecord(
                    chunk_id=i,
                    file_name=r.chunk.file_name,
                    file_type=r.chunk.file_type,
                    text=r.chunk.text,
                    metadata=r.chunk.metadata,
                )
                for i, r in enumerate(results.chunks)
            ]
        return self._keyword_search(query, top_k or settings.TOP_K_RETRIEVAL)

    def _keyword_search(self, query: str, k: int) -> List[ChunkRecord]:
        terms = set(query.lower().split())
        scored = []
        for chunk in self.chunks:
            score = sum(1 for t in terms if t in chunk.text.lower())
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:k]]

    # ── Accessors ─────────────────────────────────────────────────────────────

    def get_all_parsed_files(self) -> List[ParsedFile]:
        return self.parsed_files

    def get_file_summary(self) -> List[Dict]:
        if self._rag_pipeline is not None:
            return self._rag_pipeline.get_file_summaries()
        return [pf.to_dict() for pf in self.parsed_files]

    async def cleanup(self):
        pass
