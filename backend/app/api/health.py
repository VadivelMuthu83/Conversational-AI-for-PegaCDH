from fastapi import APIRouter, Request
from app.core.config import settings
from pathlib import Path

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    rag_pipeline   = request.app.state.rag_pipeline
    index_service  = request.app.state.index_service

    # Always read live counts from rag_pipeline (not the startup snapshot)
    live_files  = len(rag_pipeline._parsed_files)
    live_chunks = rag_pipeline._vector_store.chunk_count

    # Resolved paths — helps diagnose "files not found" issues
    files_path    = settings.files_path
    files_path_abs = str(Path(files_path).resolve())
    path_exists    = Path(files_path_abs).exists()

    return {
        "status":           "ok",
        "llm_provider":     settings.LLM_PROVIDER,
        "file_source":      settings.FILE_SOURCE,
        "indexed_files":    live_files,
        "indexed_chunks":   live_chunks,
        "streaming_enabled": settings.STREAMING_ENABLED,
        # Diagnostic fields — shown when indexed_files is 0
        "files_path":       files_path,
        "files_path_abs":   files_path_abs,
        "files_path_exists": path_exists,
        "embedding_model":  settings.embedding_model_name,
        "retrieval_mode":   settings.RETRIEVAL_MODE,
    }
