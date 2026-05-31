"""Copilot Analyst — FastAPI Application. Supports Gemini, OpenAI, Azure OpenAI, Anthropic."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, files, health
from app.api.cdh_chat import router as cdh_router
from app.api.observability import router as obs_router
from app.api.polaris import router as polaris_router
from app.cdh.cdh_parser import CDHFileParser
from app.core.config import settings
from app.core.logging import setup_logging
from app.rag.pipeline import RAGPipeline
from app.services.index_service import ChunkRecord, IndexService
from app.services.llm_provider import get_llm_provider

setup_logging()
logger = logging.getLogger(__name__)


def _resolve_files_path() -> Path:
    raw = settings.files_path
    candidates = [
        Path(raw).resolve(),
        Path(__file__).parent.parent.parent / "sample-data",
        Path(__file__).parent.parent.parent.parent / "sample-data",
        Path(__file__).parent.parent.parent / raw.lstrip("./\\"),
    ]
    for p in candidates:
        try:
            if p.exists() and any(p.iterdir()):
                return p
        except Exception:
            pass
    return Path(raw).resolve()


def _sync_index_service(index_service: IndexService, rag: RAGPipeline):
    index_service.parsed_files = rag._parsed_files
    index_service.chunks = [
        ChunkRecord(chunk_id=i, file_name=c.file_name, file_type=c.file_type,
                    text=c.text, metadata=c.metadata)
        for i, c in enumerate(rag._vector_store.get_chunks())
    ]


def _key_status(key: Optional[str]) -> str:
    return "✅ SET" if key else "❌ NOT SET"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 55)
    logger.info("  COPILOT ANALYST — STARTUP")
    logger.info("=" * 55)
    logger.info(f"  LLM_PROVIDER             : {settings.LLM_PROVIDER}")
    logger.info(f"  GEMINI_API_KEY           : {_key_status(settings.GEMINI_API_KEY)}")
    logger.info(f"  OPENAI_API_KEY           : {_key_status(settings.OPENAI_API_KEY)}")
    logger.info(f"  AZURE_OPENAI_API_KEY     : {_key_status(settings.AZURE_OPENAI_API_KEY)}")
    logger.info(f"  AZURE_OPENAI_ENDPOINT    : {settings.AZURE_OPENAI_ENDPOINT or 'NOT SET'}")
    logger.info(f"  AZURE_OPENAI_DEPLOYMENT  : {settings.AZURE_OPENAI_DEPLOYMENT}")
    logger.info(f"  ANTHROPIC_API_KEY        : {_key_status(settings.ANTHROPIC_API_KEY)}")

    abs_path = _resolve_files_path()
    logger.info(f"  Files path               : {abs_path}")
    logger.info(f"  Path exists              : {abs_path.exists()}")
    logger.info(f"  Embedding model          : {settings.embedding_model_name}")
    logger.info("=" * 55)

    if abs_path.exists():
        import app.core.config as _cfg
        _cfg.settings.KNOWLEDGE_PATH   = str(abs_path)
        _cfg.settings.LOCAL_FILES_PATH = str(abs_path)
    else:
        logger.error(
            f"❌  Data folder not found: {abs_path}\n"
            f"    Set KNOWLEDGE_PATH=<absolute path to sample-data> in backend\\.env"
        )

    llm = get_llm_provider()

    async def llm_callable(prompt: str) -> str:
        from app.services.llm_provider import LLMMessage
        return await llm.chat([LLMMessage(role="user", content=prompt)])

    rag = RAGPipeline()
    rag._parser = CDHFileParser(chunk_size=settings.CHUNK_SIZE,
                                chunk_overlap=settings.CHUNK_OVERLAP)
    await rag.initialize(llm_callable=llm_callable)

    try:
        stats = await rag.index_all()
        logger.info(
            f"✅ Index ready: {stats['files_parsed']} files, "
            f"{stats['total_chunks']} chunks"
        )
    except Exception as e:
        logger.warning(f"Indexing failed: {e}")

    index_service = IndexService()
    index_service._rag_pipeline = rag
    _sync_index_service(index_service, rag)

    app.state.rag_pipeline  = rag
    app.state.index_service = index_service
    yield
    logger.info("Shutting down…")


app = FastAPI(
    title="Copilot Analyst",
    description="AI chat for data analysis — Gemini | OpenAI | Azure OpenAI | Anthropic",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router,  prefix="/api", tags=["health"])
app.include_router(chat.router,    prefix="/api", tags=["chat"])
app.include_router(files.router,   prefix="/api", tags=["files"])
app.include_router(cdh_router,     prefix="/api", tags=["cdh"])
app.include_router(obs_router,     prefix="/api", tags=["observability"])
app.include_router(polaris_router, prefix="/api", tags=["polaris"])


@app.get("/")
async def root():
    abs_path = _resolve_files_path()
    return {
        "app":                    settings.APP_NAME,
        "version":                settings.APP_VERSION,
        "active_llm_provider":    settings.LLM_PROVIDER,
        "supported_providers":    ["gemini", "openai", "azure", "anthropic"],
        "gemini_key_set":         bool(settings.GEMINI_API_KEY),
        "openai_key_set":         bool(settings.OPENAI_API_KEY),
        "azure_key_set":          bool(settings.AZURE_OPENAI_API_KEY),
        "azure_endpoint_set":     bool(settings.AZURE_OPENAI_ENDPOINT),
        "anthropic_key_set":      bool(settings.ANTHROPIC_API_KEY),
        "files_path":             str(abs_path),
        "files_path_exists":      abs_path.exists(),
        "embedding_model":        settings.embedding_model_name,
    }


@app.get("/api/debug-env")
async def debug_env():
    """
    Shows what keys and settings the app has loaded.
    Use this endpoint to diagnose LLM key issues.
    """
    abs_path = _resolve_files_path()
    return {
        "active_provider": settings.LLM_PROVIDER,
        "providers": {
            "gemini": {
                "status":     "✅ configured" if settings.GEMINI_API_KEY else "❌ key missing",
                "model":      settings.GEMINI_MODEL,
                "env_var":    "GEMINI_API_KEY",
                "get_key_at": "https://aistudio.google.com (free)",
            },
            "openai": {
                "status":     "✅ configured" if settings.OPENAI_API_KEY else "❌ key missing",
                "model":      settings.OPENAI_MODEL,
                "env_var":    "OPENAI_API_KEY",
                "get_key_at": "https://platform.openai.com/api-keys",
            },
            "azure": {
                "status":     "✅ configured" if (settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT) else "❌ key/endpoint missing",
                "deployment": settings.AZURE_OPENAI_DEPLOYMENT,
                "endpoint":   settings.AZURE_OPENAI_ENDPOINT or "NOT SET",
                "api_version": settings.AZURE_OPENAI_API_VERSION,
                "env_vars":   ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT"],
                "get_from":   "Azure Portal → Azure OpenAI → Keys and Endpoint",
            },
            "anthropic": {
                "status":     "✅ configured" if settings.ANTHROPIC_API_KEY else "❌ key missing",
                "model":      settings.ANTHROPIC_MODEL,
                "env_var":    "ANTHROPIC_API_KEY",
                "get_key_at": "https://console.anthropic.com",
            },
        },
        "files": {
            "knowledge_path": settings.KNOWLEDGE_PATH,
            "resolved_path":  str(abs_path),
            "exists":         abs_path.exists(),
        },
        "os_environ_check": {
            "LLM_PROVIDER":           os.environ.get("LLM_PROVIDER", "NOT SET"),
            "GEMINI_API_KEY":         "SET" if os.environ.get("GEMINI_API_KEY") else "NOT SET",
            "OPENAI_API_KEY":         "SET" if os.environ.get("OPENAI_API_KEY") else "NOT SET",
            "AZURE_OPENAI_API_KEY":   "SET" if os.environ.get("AZURE_OPENAI_API_KEY") else "NOT SET",
            "AZURE_OPENAI_ENDPOINT":  os.environ.get("AZURE_OPENAI_ENDPOINT", "NOT SET"),
            "ANTHROPIC_API_KEY":      "SET" if os.environ.get("ANTHROPIC_API_KEY") else "NOT SET",
        },
        "if_still_mock_mode": (
            "If a key shows NOT SET in os_environ_check, the .env file "
            "is not being loaded. Confirm backend\\.env exists in the backend/ folder "
            "(not project root) and contains your key with no spaces around =."
        ),
    }
