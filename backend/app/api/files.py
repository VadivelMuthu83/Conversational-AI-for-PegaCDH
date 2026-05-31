"""Files API — refresh also re-syncs the index_service shim."""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.services.file_source import get_file_source

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/files")
async def list_files(request: Request):
    try:
        source = get_file_source()
        files  = source.list_files()
        return {
            "source":     settings.FILE_SOURCE,
            "path":       settings.files_path,
            "path_abs":   str(Path(settings.files_path).resolve()),
            "total":      len(files),
            "files":      [f.to_dict() for f in files],
        }
    except Exception as e:
        logger.error(f"list_files error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/indexed")
async def list_indexed_files(request: Request):
    rag_pipeline = request.app.state.rag_pipeline
    summary      = rag_pipeline.get_file_summaries()
    return {
        "total_files":       len(summary),
        "total_chunks":      rag_pipeline._vector_store.chunk_count,
        "retrieval_mode":    settings.RETRIEVAL_MODE,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_model":   settings.embedding_model_name,
        "chunk_strategy":    settings.CHUNK_STRATEGY,
        "files_path":        settings.files_path,
        "files_path_abs":    str(Path(settings.files_path).resolve()),
        "files":             summary,
    }


@router.post("/files/refresh")
async def refresh_index(request: Request):
    """Re-scan files, rebuild RAG index, sync health endpoint."""
    from app.main import _sync_index_service
    rag_pipeline  = request.app.state.rag_pipeline
    index_service = request.app.state.index_service
    try:
        stats = await rag_pipeline.index_all()
        # Keep index_service shim in sync
        _sync_index_service(index_service, rag_pipeline)
        return {
            "status":       "refreshed",
            "files_path":   settings.files_path,
            "files_path_abs": str(Path(settings.files_path).resolve()),
            **stats,
        }
    except Exception as e:
        logger.error(f"refresh_index error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
