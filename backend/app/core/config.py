"""
Central configuration — supports all four LLM providers:
  gemini     → Google Gemini (free tier available)
  openai     → OpenAI GPT-4o
  azure      → Azure OpenAI Service
  anthropic  → Anthropic Claude
"""
import os
from pathlib import Path
from typing import List, Optional


def _load_env() -> None:
    """Load .env files using python-dotenv before pydantic reads anything."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("[config] WARNING: run: pip install python-dotenv", flush=True)
        return

    this_file   = Path(__file__).resolve()
    backend_dir = this_file.parent.parent.parent   # backend/
    project_dir = backend_dir.parent               # project root

    loaded = []
    for path in [project_dir / ".env", backend_dir / ".env"]:
        if path.exists():
            load_dotenv(dotenv_path=path, override=True)
            loaded.append(str(path))

    if loaded:
        print(f"[config] Loaded .env: {loaded}", flush=True)
    else:
        print(
            f"[config] No .env found.\n"
            f"  Expected: {backend_dir / '.env'}\n"
            f"  Copy backend\\.env.template to backend\\.env and fill in your keys.",
            flush=True,
        )

    # Print resolved values for all provider keys
    provider  = os.environ.get("LLM_PROVIDER", "NOT SET")
    gemini    = os.environ.get("GEMINI_API_KEY", "")
    anthropic = os.environ.get("ANTHROPIC_API_KEY", "")
    openai    = os.environ.get("OPENAI_API_KEY", "")
    azure_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    azure_ep  = os.environ.get("AZURE_OPENAI_ENDPOINT", "")

    print(f"[config] LLM_PROVIDER            = {provider}", flush=True)
    print(f"[config] GEMINI_API_KEY          = {'SET (' + gemini[:10] + '...)' if gemini else 'NOT SET'}", flush=True)
    print(f"[config] ANTHROPIC_API_KEY       = {'SET' if anthropic else 'NOT SET'}", flush=True)
    print(f"[config] OPENAI_API_KEY          = {'SET' if openai else 'NOT SET'}", flush=True)
    print(f"[config] AZURE_OPENAI_API_KEY    = {'SET' if azure_key else 'NOT SET'}", flush=True)
    print(f"[config] AZURE_OPENAI_ENDPOINT   = {azure_ep if azure_ep else 'NOT SET'}", flush=True)


_load_env()

from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME:    str       = "Copilot Analyst"
    APP_VERSION: str       = "2.0.0"
    DEBUG:       bool      = False
    LOG_LEVEL:   str       = "INFO"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── File source ───────────────────────────────────────────────────────────
    FILE_SOURCE:      str           = "local"
    MAX_FILE_SIZE_MB: int           = 500
    KNOWLEDGE_PATH:   Optional[str] = None
    LOCAL_FILES_PATH: str           = "./sample-data"

    @property
    def files_path(self) -> str:
        return self.KNOWLEDGE_PATH or self.LOCAL_FILES_PATH

    # ── AWS S3 ────────────────────────────────────────────────────────────────
    AWS_ACCESS_KEY_ID:     Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION:            str           = "us-east-1"
    S3_BUCKET:             Optional[str] = None
    S3_PREFIX:             str           = ""

    # ── LLM: Google Gemini ────────────────────────────────────────────────────
    # Free tier: https://aistudio.google.com
    # LLM_PROVIDER=gemini
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL:   str           = "gemini-2.0-flash"

    # ── LLM: OpenAI ───────────────────────────────────────────────────────────
    # https://platform.openai.com
    # LLM_PROVIDER=openai
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL:   str           = "gpt-4o"

    # ── LLM: Azure OpenAI ─────────────────────────────────────────────────────
    # https://portal.azure.com → Azure OpenAI Service
    # LLM_PROVIDER=azure
    AZURE_OPENAI_API_KEY:  Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None   # https://<name>.openai.azure.com/
    AZURE_OPENAI_DEPLOYMENT: str         = "gpt-4o"  # your deployment name
    AZURE_OPENAI_API_VERSION: str        = "2024-02-01"

    # ── LLM: Anthropic Claude ─────────────────────────────────────────────────
    # https://console.anthropic.com
    # LLM_PROVIDER=anthropic
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL:   str           = "claude-sonnet-4-20250514"

    # Active provider — change to switch models
    LLM_PROVIDER: str = "gemini"   # gemini | openai | azure | anthropic

    # ── Embeddings ────────────────────────────────────────────────────────────
    EMBEDDING_PROVIDER:     str           = "local"
    EMBEDDING_MODEL:        Optional[str] = None
    EMBEDDING_MODEL_LOCAL:  str           = "all-MiniLM-L6-v2"
    EMBEDDING_MODEL_OPENAI: str           = "text-embedding-3-small"
    EMBEDDING_DIMENSION:    int           = 384

    @property
    def embedding_model_name(self) -> str:
        return self.EMBEDDING_MODEL or self.EMBEDDING_MODEL_LOCAL

    # ── RAG ───────────────────────────────────────────────────────────────────
    RAG_ENABLED:    bool   = True
    CHUNK_SIZE:     int    = 800
    CHUNK_OVERLAP:  int    = 150
    CHUNK_STRATEGY: str    = "recursive"
    TOP_K_RETRIEVAL: int   = 8
    TOP_K_RERANK:    int   = 4
    RETRIEVAL_MODE:  str   = "hybrid"
    HYBRID_ALPHA:    float = 0.6

    RERANKER_ENABLED:  bool          = False
    RERANKER_PROVIDER: str           = "cross-encoder"
    RERANKER_MODEL:    str           = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    COHERE_API_KEY:    Optional[str] = None

    RAG_STORE_PATH: Optional[str] = None
    INDEX_DIR:      str           = "./index"
    INDEX_PERSIST:  bool          = True

    @property
    def index_dir(self) -> str:
        return self.RAG_STORE_PATH or self.INDEX_DIR

    QUERY_EXPANSION_ENABLED: bool = False   # disabled by default (saves LLM calls)
    HYDE_ENABLED:            bool = False
    MAX_CONTEXT_TOKENS:      int  = 6000

    # ── LangSmith ─────────────────────────────────────────────────────────────
    LANGSMITH_TRACING:    bool          = False
    LANGCHAIN_TRACING_V2: bool          = False
    LANGSMITH_API_KEY:    Optional[str] = None
    LANGCHAIN_API_KEY:    Optional[str] = None
    LANGSMITH_PROJECT:    str           = "copilot-analyst"
    LANGCHAIN_PROJECT:    str           = "copilot-analyst"
    LANGSMITH_ENDPOINT:   str           = "https://api.smith.langchain.com"
    LANGCHAIN_ENDPOINT:   str           = "https://api.smith.langchain.com"

    @property
    def tracing_enabled(self) -> bool:
        return self.LANGSMITH_TRACING or self.LANGCHAIN_TRACING_V2

    @property
    def langsmith_api_key(self) -> Optional[str]:
        return self.LANGSMITH_API_KEY or self.LANGCHAIN_API_KEY

    @property
    def langsmith_project(self) -> str:
        return (
            self.LANGSMITH_PROJECT
            if self.LANGSMITH_PROJECT != "copilot-analyst"
            else self.LANGCHAIN_PROJECT
        )

    @property
    def langsmith_endpoint(self) -> str:
        return self.LANGSMITH_ENDPOINT or self.LANGCHAIN_ENDPOINT

    # ── Polaris ───────────────────────────────────────────────────────────────
    POLARIS_ENABLED:      bool          = False
    POLARIS_URI:          Optional[str] = None
    POLARIS_CREDENTIAL:   Optional[str] = None
    POLARIS_WAREHOUSE:    Optional[str] = None
    POLARIS_NAMESPACE:    Optional[str] = None
    POLARIS_CATALOG_NAME: str           = "polaris"

    # ── Performance ───────────────────────────────────────────────────────────
    MAX_WORKERS:             int  = 4
    REQUEST_TIMEOUT_SECONDS: int  = 120
    STREAMING_ENABLED:       bool = True
    PROCESSING_MODE:         str  = "async"
    BATCH_EMBED_SIZE:        int  = 64

    class Config:
        env_file          = ".env"
        env_file_encoding = "utf-8"
        case_sensitive    = False
        extra             = "ignore"


settings = Settings()
