"""
Text chunking strategies:
  - fixed     : simple sliding window
  - recursive : split on paragraph → sentence → word boundaries (recommended)
  - semantic  : cluster sentences by embedding similarity (expensive but best quality)

All strategies return List[Chunk] with position metadata for parent-child linking.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    file_name: str
    file_type: str
    metadata: dict = field(default_factory=dict)

    # parent-doc link (set by ParentChildChunker)
    parent_id: Optional[str] = None

    @property
    def id(self) -> str:
        return f"{self.file_name}::{self.chunk_index}"


# ─── Fixed-size chunker ───────────────────────────────────────────────────────

class FixedChunker:
    def __init__(self, size: int = None, overlap: int = None):
        self.size = size or settings.CHUNK_SIZE
        self.overlap = overlap or settings.CHUNK_OVERLAP

    def chunk(self, text: str, file_name: str, file_type: str,
              metadata: dict = None) -> List[Chunk]:
        chunks = []
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + self.size, len(text))
            chunks.append(Chunk(
                text=text[start:end],
                chunk_index=idx,
                start_char=start,
                end_char=end,
                file_name=file_name,
                file_type=file_type,
                metadata=metadata or {},
            ))
            start += self.size - self.overlap
            idx += 1
        return chunks


# ─── Recursive chunker (default — best balance) ───────────────────────────────

class RecursiveChunker:
    """
    Tries to split on paragraph breaks first, then sentence boundaries,
    then word boundaries, finally character boundaries.
    Produces semantically cleaner chunks than fixed-size.
    """

    SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""]

    def __init__(self, size: int = None, overlap: int = None):
        self.size = size or settings.CHUNK_SIZE
        self.overlap = overlap or settings.CHUNK_OVERLAP

    def chunk(self, text: str, file_name: str, file_type: str,
              metadata: dict = None) -> List[Chunk]:
        raw_chunks = self._split(text, self.SEPARATORS)
        # Merge small chunks and add overlap
        merged = self._merge_and_overlap(raw_chunks)
        result = []
        pos = 0
        for idx, c in enumerate(merged):
            start = text.find(c, pos)
            if start == -1:
                start = pos
            end = start + len(c)
            result.append(Chunk(
                text=c,
                chunk_index=idx,
                start_char=start,
                end_char=end,
                file_name=file_name,
                file_type=file_type,
                metadata=metadata or {},
            ))
            pos = max(pos, end - self.overlap)
        return result

    def _split(self, text: str, separators: List[str]) -> List[str]:
        if not separators:
            return [text[i:i + self.size] for i in range(0, len(text), self.size)]

        sep = separators[0]
        rest = separators[1:]

        if sep == "":
            return [text[i:i + self.size] for i in range(0, len(text), self.size)]

        parts = text.split(sep)
        good, bad = [], []
        for p in parts:
            if len(p) <= self.size:
                good.append(p)
            else:
                bad.append(p)

        final = []
        for p in parts:
            if len(p) <= self.size:
                if p.strip():
                    final.append(p)
            else:
                sub = self._split(p, rest)
                final.extend(sub)
        return final

    def _merge_and_overlap(self, chunks: List[str]) -> List[str]:
        merged = []
        current = ""
        for c in chunks:
            candidate = (current + "\n" + c).strip() if current else c.strip()
            if len(candidate) <= self.size:
                current = candidate
            else:
                if current:
                    merged.append(current)
                # overlap: keep tail of current
                tail = current[-self.overlap:] if self.overlap and current else ""
                current = (tail + "\n" + c).strip() if tail else c.strip()
        if current:
            merged.append(current)
        return merged


# ─── Semantic chunker (optional — uses embeddings) ────────────────────────────

class SemanticChunker:
    """
    Splits text into sentences then groups them by embedding cosine similarity.
    Requires embeddings; falls back to RecursiveChunker if unavailable.
    """

    def __init__(self, threshold: float = 0.8, size: int = None, overlap: int = None):
        self.threshold = threshold
        self.size = size or settings.CHUNK_SIZE
        self.overlap = overlap or settings.CHUNK_OVERLAP
        self._fallback = RecursiveChunker(size, overlap)

    def chunk(self, text: str, file_name: str, file_type: str,
              metadata: dict = None) -> List[Chunk]:
        try:
            return self._semantic_chunk(text, file_name, file_type, metadata)
        except Exception as e:
            logger.warning(f"Semantic chunking failed ({e}); using recursive fallback")
            return self._fallback.chunk(text, file_name, file_type, metadata)

    def _semantic_chunk(self, text, file_name, file_type, metadata):
        import numpy as np
        from sentence_transformers import SentenceTransformer

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        if len(sentences) < 3:
            return self._fallback.chunk(text, file_name, file_type, metadata)

        # Use resolved property: EMBEDDING_MODEL → EMBEDDING_MODEL_LOCAL
        model = SentenceTransformer(settings.embedding_model_name)
        embs = model.encode(sentences, normalize_embeddings=True)

        # Cosine similarity between consecutive sentences
        groups = [[sentences[0]]]
        for i in range(1, len(sentences)):
            sim = float(np.dot(embs[i - 1], embs[i]))
            if sim >= self.threshold:
                groups[-1].append(sentences[i])
            else:
                groups.append([sentences[i]])

        chunks = []
        pos = 0
        for idx, grp in enumerate(groups):
            chunk_text = " ".join(grp)
            start = text.find(grp[0], pos)
            if start == -1:
                start = pos
            end = start + len(chunk_text)
            chunks.append(Chunk(
                text=chunk_text,
                chunk_index=idx,
                start_char=start,
                end_char=end,
                file_name=file_name,
                file_type=file_type,
                metadata=metadata or {},
            ))
            pos = max(pos, end - self.overlap)
        return chunks


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_chunker(strategy: str = None):
    s = (strategy or settings.CHUNK_STRATEGY).lower()
    if s == "semantic":
        return SemanticChunker()
    elif s == "fixed":
        return FixedChunker()
    else:
        return RecursiveChunker()
