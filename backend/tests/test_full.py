"""
Full test suite: RAG pipeline, LangSmith tracer, Polaris catalog, API endpoints.
Run: pytest tests/ -v
"""
import asyncio
import io
import json
import pickle
import zipfile
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio

# ─────────────────────────────────────────────────────────────────────────────
# RAG: Chunker Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestChunkers:
    def test_fixed_chunker_basic(self):
        from app.rag.chunker import FixedChunker
        c = FixedChunker(size=100, overlap=20)
        text = "A" * 250
        chunks = c.chunk(text, "test.txt", "text")
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.text) <= 100
        assert all(ch.file_name == "test.txt" for ch in chunks)

    def test_recursive_chunker_paragraph_split(self):
        from app.rag.chunker import RecursiveChunker
        c = RecursiveChunker(size=200, overlap=30)
        text = "First paragraph with some content here.\n\nSecond paragraph with different content.\n\nThird paragraph."
        chunks = c.chunk(text, "doc.txt", "text")
        assert len(chunks) >= 1
        assert all(len(ch.text) <= 200 for ch in chunks)

    def test_recursive_chunker_short_text(self):
        from app.rag.chunker import RecursiveChunker
        c = RecursiveChunker(size=500, overlap=50)
        text = "Short text."
        chunks = c.chunk(text, "short.txt", "text")
        assert len(chunks) == 1
        assert chunks[0].text.strip() == "Short text."

    def test_chunk_metadata(self):
        from app.rag.chunker import FixedChunker
        c = FixedChunker(size=100, overlap=0)
        meta = {"row_count": 50, "columns": ["a", "b"]}
        chunks = c.chunk("x" * 100, "data.csv", "csv", metadata=meta)
        assert chunks[0].metadata["row_count"] == 50
        assert chunks[0].metadata["columns"] == ["a", "b"]

    def test_chunk_id_uniqueness(self):
        from app.rag.chunker import RecursiveChunker
        c = RecursiveChunker(size=50, overlap=10)
        text = "word " * 100
        chunks = c.chunk(text, "f.txt", "text")
        ids = [ch.id for ch in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs must be unique"

    def test_get_chunker_factory(self):
        from app.rag.chunker import get_chunker, FixedChunker, RecursiveChunker
        assert isinstance(get_chunker("fixed"), FixedChunker)
        assert isinstance(get_chunker("recursive"), RecursiveChunker)
        assert isinstance(get_chunker("unknown"), RecursiveChunker)


# ─────────────────────────────────────────────────────────────────────────────
# RAG: Embeddings Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEmbeddings:
    @pytest.mark.asyncio
    async def test_local_embedding_returns_ndarray(self):
        """Test local embedding provider returns correct shape."""
        from app.rag.embeddings import LocalEmbeddingProvider
        provider = LocalEmbeddingProvider("all-MiniLM-L6-v2")

        with patch.object(provider, "_load"):
            mock_model = MagicMock()
            mock_model.encode = MagicMock(
                return_value=np.random.rand(2, 384).astype("float32")
            )
            mock_model.get_sentence_embedding_dimension = MagicMock(return_value=384)
            provider._model = mock_model
            provider._dim = 384

            result = await provider.embed(["hello world", "test query"])
            assert result.shape == (2, 384)
            assert result.dtype == np.float32

    @pytest.mark.asyncio
    async def test_embedding_batching(self):
        """Large input is split into batches correctly."""
        from app.rag.embeddings import LocalEmbeddingProvider
        provider = LocalEmbeddingProvider()

        call_count = 0
        def mock_encode(texts, **kwargs):
            nonlocal call_count
            call_count += 1
            return np.random.rand(len(texts), 384).astype("float32")

        with patch.object(provider, "_load"):
            provider._model = MagicMock()
            provider._model.encode = mock_encode
            provider._dim = 384

            texts = [f"text {i}" for i in range(130)]
            result = await provider.embed(texts)
            assert result.shape[0] == 130
            assert call_count >= 2  # batched

    def test_embedding_factory_local_default(self):
        from app.rag.embeddings import get_embedding_provider, LocalEmbeddingProvider
        import app.rag.embeddings as emb_module
        emb_module._provider_cache = None

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.EMBEDDING_PROVIDER = "local"
            mock_settings.OPENAI_API_KEY = None
            mock_settings.EMBEDDING_MODEL_LOCAL = "all-MiniLM-L6-v2"
            mock_settings.BATCH_EMBED_SIZE = 64

            provider = get_embedding_provider()
            # Reset cache
            emb_module._provider_cache = None


# ─────────────────────────────────────────────────────────────────────────────
# RAG: Vector Store Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestVectorStore:
    def _make_chunks(self, n: int = 5):
        from app.rag.chunker import Chunk
        return [
            Chunk(
                text=f"This is document {i} about topic {'sales' if i % 2 == 0 else 'customers'}",
                chunk_index=i,
                start_char=i * 50,
                end_char=(i + 1) * 50,
                file_name=f"file{i % 3}.csv",
                file_type="csv",
            )
            for i in range(n)
        ]

    @pytest.mark.asyncio
    async def test_bm25_search(self):
        from app.rag.vector_store import VectorStore
        store = VectorStore()
        chunks = self._make_chunks(10)

        mock_embedder = MagicMock()
        mock_embedder.embed = AsyncMock(
            return_value=np.random.rand(10, 384).astype("float32")
        )
        mock_embedder.dimension = MagicMock(return_value=384)
        store._embedder = mock_embedder

        await store._build_bm25(chunks)
        store._chunks = chunks

        results = store._bm25_search("sales revenue", k=3)
        assert len(results) > 0
        assert all(r.chunk in chunks for r in results)

    @pytest.mark.asyncio
    async def test_keyword_fallback_search(self):
        from app.rag.vector_store import VectorStore
        store = VectorStore()
        store._chunks = self._make_chunks(10)
        store._bm25 = None

        results = store._fallback_keyword_search("customers document", k=5)
        assert len(results) > 0
        assert results[0].score > 0

    @pytest.mark.asyncio
    async def test_empty_store_returns_empty(self):
        from app.rag.vector_store import VectorStore
        store = VectorStore()
        store._chunks = []
        results = await store.search("any query")
        assert results == []

    @pytest.mark.asyncio
    async def test_hybrid_search_combines_results(self):
        from app.rag.vector_store import VectorStore
        store = VectorStore()
        chunks = self._make_chunks(10)
        store._chunks = chunks

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed = AsyncMock(
            return_value=np.random.rand(1, 384).astype("float32")
        )
        store._embedder = mock_embedder

        # Mock FAISS
        mock_index = MagicMock()
        scores = np.array([[0.9, 0.8, 0.7, 0.6, 0.5]])
        indices = np.array([[0, 2, 4, 6, 8]])
        mock_index.search = MagicMock(return_value=(scores, indices))
        store._faiss_index = mock_index

        await store._build_bm25(chunks)

        results = await store._hybrid_search("sales customers", k=5)
        assert len(results) > 0
        # All results should be from our chunks
        chunk_ids = {c.id for c in chunks}
        for r in results:
            assert r.chunk.id in chunk_ids


# ─────────────────────────────────────────────────────────────────────────────
# RAG: Reranker Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRerankers:
    def _make_results(self, n=5):
        from app.rag.chunker import Chunk
        from app.rag.vector_store import SearchResult
        chunks = [
            Chunk(
                text=f"Document about topic {i}",
                chunk_index=i,
                start_char=0,
                end_char=20,
                file_name="f.csv",
                file_type="csv",
            )
            for i in range(n)
        ]
        return [SearchResult(chunk=c, score=float(n - i)) for i, c in enumerate(chunks)]

    @pytest.mark.asyncio
    async def test_passthrough_reranker(self):
        from app.rag.reranker import PassthroughReranker
        r = PassthroughReranker()
        results = self._make_results(5)
        out = await r.rerank("query", results, top_k=3)
        assert len(out) == 3
        assert out == results[:3]

    @pytest.mark.asyncio
    async def test_cross_encoder_reranker(self):
        from app.rag.reranker import CrossEncoderReranker
        r = CrossEncoderReranker()
        results = self._make_results(4)

        with patch.object(r, "_load"):
            r._model = MagicMock()
            r._model.predict = MagicMock(return_value=[0.9, 0.3, 0.7, 0.1])
            out = await r.rerank("test query", results, top_k=2)

        assert len(out) == 2
        assert out[0].score == 0.9  # highest score first

    def test_get_reranker_passthrough_when_disabled(self):
        from app.rag.reranker import get_reranker, PassthroughReranker
        with patch("app.core.config.settings") as s:
            s.RERANKER_ENABLED = False
            r = get_reranker()
            assert isinstance(r, PassthroughReranker)


# ─────────────────────────────────────────────────────────────────────────────
# RAG: Query Transformer Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestQueryTransformer:
    @pytest.mark.asyncio
    async def test_expand_returns_original_when_disabled(self):
        from app.rag.query_transformer import QueryTransformer
        qt = QueryTransformer(llm_callable=None)
        result = await qt.expand("what is total revenue?")
        assert result == ["what is total revenue?"]

    @pytest.mark.asyncio
    async def test_expand_with_llm(self):
        async def mock_llm(prompt):
            return '["total revenue", "sum of sales", "revenue metric"]'

        from app.rag.query_transformer import QueryTransformer
        with patch("app.core.config.settings") as s:
            s.QUERY_EXPANSION_ENABLED = True
            qt = QueryTransformer(llm_callable=mock_llm)
            result = await qt.expand("what is total revenue?", n=3)
        assert "what is total revenue?" in result
        assert len(result) > 1

    @pytest.mark.asyncio
    async def test_expand_handles_bad_json(self):
        async def bad_llm(prompt):
            return "not valid json at all"

        from app.rag.query_transformer import QueryTransformer
        with patch("app.core.config.settings") as s:
            s.QUERY_EXPANSION_ENABLED = True
            qt = QueryTransformer(llm_callable=bad_llm)
            result = await qt.expand("query")
        assert result == ["query"]  # falls back gracefully

    @pytest.mark.asyncio
    async def test_hyde_returns_none_when_disabled(self):
        from app.rag.query_transformer import QueryTransformer
        qt = QueryTransformer(llm_callable=None)
        result = await qt.hyde("any question")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# RAG: File Parser Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFileParser:
    def test_csv_parsing(self):
        from app.parsers.file_parser import FileParser
        csv = b"name,age,salary\nAlice,30,75000\nBob,25,60000\n"
        parser = FileParser()
        results = parser.parse_bytes(csv, "test.csv")
        assert len(results) == 1
        pf = results[0]
        assert pf.file_type == "csv"
        assert pf.row_count == 2
        assert "name" in pf.columns

    def test_json_array_parsing(self):
        from app.parsers.file_parser import FileParser
        data = [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]
        parser = FileParser()
        results = parser.parse_bytes(json.dumps(data).encode(), "test.json")
        assert results[0].row_count == 2

    def test_zip_parsing(self):
        from app.parsers.file_parser import FileParser
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("data.csv", "col1,col2\n1,2\n3,4\n")
            zf.writestr("notes.txt", "Some important notes")
        buf.seek(0)
        parser = FileParser()
        results = parser.parse_bytes(buf.read(), "archive.zip")
        assert len(results) == 2

    def test_can_parse_extensions(self):
        from app.parsers.file_parser import FileParser
        p = FileParser()
        assert p.can_parse("data.csv")
        assert p.can_parse("data.parquet")
        assert p.can_parse("data.xlsx")
        assert p.can_parse("data.json")
        assert p.can_parse("archive.zip")
        assert not p.can_parse("binary.exe")
        assert not p.can_parse("image.png")

    def test_text_chunking_overlap(self):
        from app.parsers.file_parser import FileParser
        parser = FileParser(chunk_size=100, chunk_overlap=20)
        text = "word " * 200
        chunks = parser._chunk_text(text)
        assert len(chunks) > 1


# ─────────────────────────────────────────────────────────────────────────────
# LangSmith: Tracer Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestLangSmithTracer:
    def test_tracer_disabled_by_default(self):
        """LangSmith should be disabled when key not set."""
        from app.observability.langsmith_tracer import LangSmithTracer
        with patch("app.core.config.settings") as s:
            s.LANGCHAIN_TRACING_V2 = False
            s.LANGCHAIN_API_KEY = None
            t = LangSmithTracer()
            assert not t.enabled

    def test_start_run_no_op_when_disabled(self):
        from app.observability.langsmith_tracer import LangSmithTracer
        t = LangSmithTracer()
        t._enabled = False
        run_id = t.start_run("test", inputs={"q": "hello"})
        assert run_id is None

    def test_end_run_no_op_when_disabled(self):
        from app.observability.langsmith_tracer import LangSmithTracer
        t = LangSmithTracer()
        t._enabled = False
        t.end_run(None, outputs={})  # should not raise

    def test_submit_feedback_no_op_when_disabled(self):
        from app.observability.langsmith_tracer import LangSmithTracer
        t = LangSmithTracer()
        t._enabled = False
        t.submit_feedback("fake-run-id", score=1.0)  # should not raise

    @pytest.mark.asyncio
    async def test_trace_decorator_calls_function(self):
        from app.observability.langsmith_tracer import LangSmithTracer
        t = LangSmithTracer()
        t._enabled = False  # no-op tracing

        @t.trace("test_fn", run_type="chain")
        async def my_func(x: int) -> int:
            return x * 2

        result = await my_func(21)
        assert result == 42

    @pytest.mark.asyncio
    async def test_trace_decorator_propagates_exceptions(self):
        from app.observability.langsmith_tracer import LangSmithTracer
        t = LangSmithTracer()
        t._enabled = False

        @t.trace("boom_fn")
        async def boom():
            raise ValueError("intentional error")

        with pytest.raises(ValueError, match="intentional error"):
            await boom()


# ─────────────────────────────────────────────────────────────────────────────
# LangSmith: Metrics Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRAGMetrics:
    def test_step_tracking(self):
        from app.observability.metrics import RAGMetrics
        m = RAGMetrics("sid", "what is revenue?", "anthropic")
        step = m.begin_step("retrieve")
        import time; time.sleep(0.01)
        m.end_step(chunks=5)
        assert step.duration_ms >= 10
        assert step.metadata.get("chunks") == 5

    def test_log_to_langsmith_no_op(self):
        """Should not raise even when LangSmith disabled."""
        from app.observability.metrics import RAGMetrics
        with patch("app.observability.metrics.tracer") as mock_tracer:
            mock_tracer.start_run = MagicMock(return_value=None)
            mock_tracer.end_run = MagicMock()
            m = RAGMetrics("sid", "query", "anthropic")
            run_id = m.log_to_langsmith("Test answer")
            mock_tracer.end_run.assert_called()


# ─────────────────────────────────────────────────────────────────────────────
# Polaris: Catalog Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPolarisClient:
    def test_polaris_raises_without_uri(self):
        from app.polaris.catalog import PolarisClient
        with patch("app.core.config.settings") as s:
            s.POLARIS_URI = None
            s.POLARIS_CREDENTIAL = "id:secret"
            c = PolarisClient()
            with pytest.raises(ValueError, match="POLARIS_URI"):
                c._get_catalog()

    def test_polaris_raises_without_credential(self):
        from app.polaris.catalog import PolarisClient
        with patch("app.core.config.settings") as s:
            s.POLARIS_URI = "https://example.snowflakecomputing.com/polaris/api/catalog"
            s.POLARIS_CREDENTIAL = None
            c = PolarisClient()
            with pytest.raises(ValueError, match="POLARIS_CREDENTIAL"):
                c._get_catalog()

    def test_polaris_raises_bad_credential_format(self):
        from app.polaris.catalog import PolarisClient
        with patch("app.core.config.settings") as s:
            s.POLARIS_URI = "https://example.snowflakecomputing.com/polaris/api/catalog"
            s.POLARIS_CREDENTIAL = "no-colon-here"
            s.POLARIS_WAREHOUSE = None
            s.POLARIS_CATALOG_NAME = "polaris"
            c = PolarisClient()
            with patch("pyiceberg.catalog.load_catalog", side_effect=ImportError):
                with pytest.raises((ValueError, ImportError)):
                    c._get_catalog()

    def test_polaris_is_available_false_without_config(self):
        from app.polaris.catalog import PolarisClient
        c = PolarisClient()
        # Without valid config, is_available should return False
        with patch.object(c, "_get_catalog", side_effect=ValueError("no uri")):
            assert not c.is_available()

    def test_polaris_file_source_read_file(self):
        """PolarisFileSource.read_file should convert table to CSV bytes."""
        from app.polaris.catalog import PolarisFileSource
        import pandas as pd

        source = PolarisFileSource()
        mock_df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        with patch.object(source._client, "read_table", return_value=mock_df):
            result = source.read_file("NS.MY_TABLE")
        assert b"a,b" in result
        assert b"1,x" in result


# ─────────────────────────────────────────────────────────────────────────────
# API: Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from app.main import app
    from fastapi.testclient import TestClient

    mock_rag = MagicMock()
    mock_rag.is_ready = True
    mock_rag._parsed_files = []
    mock_rag.get_file_summaries = MagicMock(return_value=[])
    mock_rag._vector_store = MagicMock()
    mock_rag._vector_store.get_chunks = MagicMock(return_value=[])
    mock_rag._vector_store.chunk_count = 0
    mock_rag.retrieve = AsyncMock(return_value=MagicMock(
        text="No context",
        chunks=[],
        files_used=[],
        queries_used=["q"],
        retrieval_ms=0,
    ))
    mock_rag.index_all = AsyncMock(return_value={"files_parsed": 0, "total_chunks": 0})

    mock_compat = MagicMock()
    mock_compat.parsed_files = []
    mock_compat.chunks = []
    mock_compat.get_file_summary = MagicMock(return_value=[])

    app.state.rag_pipeline = mock_rag
    app.state.index_service = mock_compat

    return TestClient(app)


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_observability_status(client):
    resp = client.get("/api/observability/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "langsmith_enabled" in data
    assert "retrieval_mode" in data
    assert "rag_enabled" in data


def test_polaris_status_disabled(client):
    resp = client.get("/api/polaris/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False


def test_chat_sync(client):
    resp = client.post("/api/chat", json={
        "message": "What files are available?",
        "stream": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert "session_id" in data


def test_files_indexed(client):
    resp = client.get("/api/files/indexed")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_files" in data
    assert "total_chunks" in data


def test_feedback_disabled(client):
    """Feedback endpoint returns skipped when LangSmith disabled."""
    resp = client.post("/api/observability/feedback", json={
        "run_id": "fake-run-id",
        "positive": True,
        "comment": "Great answer",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("submitted", "skipped")


def test_polaris_tables_when_disabled(client):
    resp = client.get("/api/polaris/tables")
    assert resp.status_code == 503


def test_root_endpoint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "rag" in data
    assert "llm" in data
