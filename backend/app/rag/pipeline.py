"""
RAG Pipeline v2 — Parse → Chunk → Embed → Index → Retrieve → Rerank
Handles two content types from KNOWLEDGE_PATH:
  - Data files  (CSV/JSON/XLSX/Parquet) → CDHFileParser
  - KB articles (PDF/DOCX/MD/HTML/TXT)  → KnowledgeArticleParser
"""
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from app.core.config import settings
from app.parsers.file_parser import FileParser, ParsedFile
from app.rag.chunker import Chunk, get_chunker
from app.rag.query_transformer import QueryTransformer
from app.rag.reranker import get_reranker
from app.rag.vector_store import SearchResult, VectorStore
from app.services.file_source import FileInfo, get_file_source

logger = logging.getLogger(__name__)

DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".html", ".htm", ".md", ".txt"}
DATA_EXTENSIONS     = {".csv", ".tsv", ".xlsx", ".xls", ".parquet",
                       ".json", ".jsonl", ".zip", ".yaml", ".yml", ".xml", ".log"}


class RAGContext:
    def __init__(self, text, chunks, files_used, queries_used, retrieval_ms):
        self.text         = text
        self.chunks       = chunks
        self.files_used   = files_used
        self.queries_used = queries_used
        self.retrieval_ms = retrieval_ms

    def to_dict(self):
        return {
            "files_used":   self.files_used,
            "chunk_count":  len(self.chunks),
            "queries_used": self.queries_used,
            "retrieval_ms": self.retrieval_ms,
        }


class RAGPipeline:
    def __init__(self):
        self._vector_store    = VectorStore()
        self._parser          = FileParser(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        self._kb_parser       = None
        self._chunker         = get_chunker(settings.CHUNK_STRATEGY)
        self._reranker        = get_reranker()
        self._query_transformer: Optional[QueryTransformer] = None
        self._parsed_files:   List[ParsedFile] = []
        self._ready           = False

    # ── Init ──────────────────────────────────────────────────────────────────

    async def initialize(self, llm_callable=None):
        """Load embedder, restore persisted index if it exists."""
        self._query_transformer = QueryTransformer(llm_callable)
        await self._vector_store.initialize()

        try:
            from app.cdh.knowledge_articles import KnowledgeArticleParser
            self._kb_parser = KnowledgeArticleParser(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
            )
            logger.info("KnowledgeArticleParser ready")
        except Exception as e:
            logger.warning(f"KnowledgeArticleParser unavailable: {e}")

        if self._vector_store.chunk_count > 0:
            logger.info(
                f"RAG restored from disk: {self._vector_store.chunk_count} chunks — "
                f"will also re-scan files to rebuild _parsed_files metadata"
            )
            # Even when restoring from disk we need _parsed_files populated
            # so health endpoint and file listing work correctly.
            # Do a lightweight metadata-only scan (no re-embedding).
            await self._scan_files_metadata_only()
            self._ready = True

    async def _scan_files_metadata_only(self):
        """
        Populate _parsed_files by scanning the file source without
        re-building the vector index.  Used after restoring from disk.
        """
        try:
            source      = get_file_source()
            file_list   = source.list_files()
            max_bytes   = settings.MAX_FILE_SIZE_MB * 1024 * 1024
            parsed      = []
            for fi in file_list:
                if not self._can_parse(fi.name) or fi.size > max_bytes:
                    continue
                try:
                    content = await asyncio.to_thread(source.read_file, fi.path)
                    results = await asyncio.to_thread(
                        self._parser.parse_bytes, content, fi.name
                    )
                    parsed.extend(results)
                except Exception as e:
                    logger.debug(f"Metadata scan skip {fi.name}: {e}")
            self._parsed_files = parsed
            logger.info(
                f"Metadata scan complete: {len(self._parsed_files)} files "
                f"(chunks already loaded from disk)"
            )
        except Exception as e:
            logger.warning(f"Metadata scan failed: {e}")

    # ── Indexing ──────────────────────────────────────────────────────────────

    async def index_all(self) -> Dict:
        """Scan file source, parse everything, build full vector index."""
        t0        = time.time()
        source    = get_file_source()
        file_list = source.list_files()

        logger.info(
            f"Indexing {len(file_list)} files "
            f"from: {settings.files_path}"
        )

        self._parsed_files = []
        all_chunks: List[Chunk] = []
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        sem       = asyncio.Semaphore(settings.MAX_WORKERS)

        async def bounded(fi: FileInfo):
            async with sem:
                await self._index_file(source, fi, all_chunks, max_bytes)

        parseable = [fi for fi in file_list if self._can_parse(fi.name)]
        logger.info(f"Parseable files: {len(parseable)} / {len(file_list)}")

        await asyncio.gather(
            *[bounded(fi) for fi in parseable],
            return_exceptions=True,
        )

        await self._vector_store.build(all_chunks)
        self._ready = True

        elapsed = int((time.time() - t0) * 1000)
        stats   = {
            "files_parsed":  len(self._parsed_files),
            "total_chunks":  len(all_chunks),
            "index_time_ms": elapsed,
            "files_path":    settings.files_path,
            "index_dir":     settings.index_dir,
            "embed_model":   settings.embedding_model_name,
        }
        logger.info(f"Indexing complete: {stats}")
        return stats

    def _can_parse(self, filename: str) -> bool:
        ext = Path(filename).suffix.lower()
        return ext in DATA_EXTENSIONS or ext in DOCUMENT_EXTENSIONS

    async def _index_file(
        self,
        source,
        fi: FileInfo,
        all_chunks: List[Chunk],
        max_bytes: int,
    ):
        ext = Path(fi.name).suffix.lower()
        if fi.size > max_bytes:
            logger.warning(f"Skipping large file ({fi.size}B): {fi.name}")
            return
        try:
            content = await asyncio.to_thread(source.read_file, fi.path)

            if ext in DOCUMENT_EXTENSIONS and self._kb_parser is not None:
                # ── KB article path ──────────────────────────────────────
                chunk_dicts = await asyncio.to_thread(
                    self._kb_parser.parse, content, fi.name
                )
                for i, cd in enumerate(chunk_dicts):
                    all_chunks.append(Chunk(
                        text=cd["text"],
                        chunk_index=i,
                        start_char=0,
                        end_char=len(cd["text"]),
                        file_name=fi.name,
                        file_type=cd["metadata"].get("article_type", "document"),
                        metadata=cd["metadata"],
                    ))
                self._parsed_files.append(ParsedFile(
                    name=fi.name,
                    file_type=(
                        chunk_dicts[0]["metadata"].get("article_type", "document")
                        if chunk_dicts else "document"
                    ),
                    text_chunks=[cd["text"] for cd in chunk_dicts],
                    summary=f"KB Article | {len(chunk_dicts)} chunks",
                ))
                logger.info(f"KB article: {fi.name} → {len(chunk_dicts)} chunks")

            else:
                # ── Data file path ───────────────────────────────────────
                parsed_list = await asyncio.to_thread(
                    self._parser.parse_bytes, content, fi.name
                )
                for pf in parsed_list:
                    self._parsed_files.append(pf)
                    for j, text_chunk in enumerate(pf.text_chunks):
                        meta = {
                            "row_count":    pf.row_count,
                            "columns":      pf.columns,
                            "summary":      pf.summary,
                            "is_kb_article": False,
                        }
                        if hasattr(pf, "cdh_metadata"):
                            meta.update(pf.cdh_metadata)
                        sub_chunks = self._chunker.chunk(
                            text=text_chunk,
                            file_name=pf.name,
                            file_type=pf.file_type,
                            metadata=meta,
                        )
                        all_chunks.extend(sub_chunks)
                logger.debug(f"Data file: {fi.name} → {len(parsed_list)} parsed")

        except Exception as e:
            logger.error(f"Error indexing {fi.name}: {e}", exc_info=True)

    # ── Retrieval ─────────────────────────────────────────────────────────────

    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_files: Optional[List[str]] = None,
        kb_only: bool = False,
        data_only: bool = False,
    ) -> RAGContext:
        t0 = time.time()
        k  = top_k or settings.TOP_K_RETRIEVAL

        if not self._ready or self._vector_store.chunk_count == 0:
            return RAGContext(
                text="No files are indexed yet. "
                     "Check that KNOWLEDGE_PATH points to your data folder "
                     "and call POST /api/files/refresh to index.",
                chunks=[], files_used=[], queries_used=[query], retrieval_ms=0,
            )

        queries   = await self._query_transformer.expand(query, n=3)
        hyde_doc  = await self._query_transformer.hyde(query)
        if hyde_doc:
            queries = [hyde_doc] + queries

        all_results: List[SearchResult] = []
        for q in queries:
            results = await self._vector_store.search(q, top_k=k)
            all_results.extend(results)

        seen:   Set[str]          = set()
        unique: List[SearchResult] = []
        for r in all_results:
            if r.chunk.id not in seen:
                seen.add(r.chunk.id)
                unique.append(r)

        if kb_only:
            unique = [r for r in unique if r.chunk.metadata.get("is_kb_article", False)]
        elif data_only:
            unique = [r for r in unique if not r.chunk.metadata.get("is_kb_article", False)]
        if filter_files:
            unique = [r for r in unique if r.chunk.file_name in filter_files]

        final      = await self._reranker.rerank(query, unique, top_k=settings.TOP_K_RERANK)
        ctx_text   = self._format_context(final)
        files_used = list({r.chunk.file_name for r in final})

        return RAGContext(
            text=ctx_text,
            chunks=final,
            files_used=files_used,
            queries_used=queries,
            retrieval_ms=int((time.time() - t0) * 1000),
        )

    def _format_context(self, results: List[SearchResult]) -> str:
        if not results:
            return "No relevant context found."
        parts = []
        total = 0
        for i, r in enumerate(results):
            is_kb    = r.chunk.metadata.get("is_kb_article", False)
            art_type = r.chunk.metadata.get("article_type", r.chunk.file_type)
            section  = r.chunk.metadata.get("section", "")
            header   = (
                f"[SOURCE {i+1}] {'KB Article' if is_kb else 'Data'}"
                f" | Type: {art_type}"
                f" | File: {r.chunk.file_name}"
                + (f" | Section: {section}" if section else "")
                + f" | Score: {r.score:.3f}"
            )
            block = f"{header}\n{r.chunk.text}"
            if total + len(block) > settings.MAX_CONTEXT_TOKENS:
                remaining = settings.MAX_CONTEXT_TOKENS - total
                if remaining > 200:
                    parts.append(block[:remaining] + "\n…[truncated]")
                break
            parts.append(block)
            total += len(block)
        return "\n\n---\n\n".join(parts)

    # ── Accessors ─────────────────────────────────────────────────────────────

    def get_file_summaries(self) -> List[Dict]:
        return [pf.to_dict() for pf in self._parsed_files]

    @property
    def chunk_count(self) -> int:
        return self._vector_store.chunk_count

    @property
    def is_ready(self) -> bool:
        return self._ready
