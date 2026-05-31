"""
Observability API — LangSmith feedback, metrics, config status.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.observability.langsmith_tracer import tracer
from app.observability.metrics import log_rag_example, submit_user_feedback

router = APIRouter()
logger = logging.getLogger(__name__)


class FeedbackRequest(BaseModel):
    run_id: str
    positive: bool
    comment: Optional[str] = None


class EvalExampleRequest(BaseModel):
    query: str
    answer: str
    files_used: List[str] = []


@router.get("/observability/status")
async def observability_status():
    return {
        # LangSmith — shows resolved values regardless of which naming convention was used
        "langsmith_enabled": tracer.enabled,
        "langsmith_project": settings.langsmith_project if tracer.enabled else None,
        "langsmith_endpoint": settings.langsmith_endpoint if tracer.enabled else None,
        # Env var convention detected
        "langsmith_key_source": (
            "LANGSMITH_API_KEY" if settings.LANGSMITH_API_KEY
            else "LANGCHAIN_API_KEY" if settings.LANGCHAIN_API_KEY   # both field names accepted
            else "not set"
        ),
        "langsmith_endpoint": settings.langsmith_endpoint if tracer.enabled else None,
        # RAG
        "rag_enabled": settings.RAG_ENABLED,
        "retrieval_mode": settings.RETRIEVAL_MODE,
        "reranker_enabled": settings.RERANKER_ENABLED,
        "query_expansion": settings.QUERY_EXPANSION_ENABLED,
        "hyde_enabled": settings.HYDE_ENABLED,
        # Paths resolved
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_model": settings.embedding_model_name,
        "chunk_strategy": settings.CHUNK_STRATEGY,
        "index_dir": settings.index_dir,
        "files_path": settings.files_path,
    }


@router.post("/observability/feedback")
async def submit_feedback(req: FeedbackRequest):
    if not tracer.enabled:
        return {"status": "skipped", "reason": "LangSmith not enabled"}
    try:
        submit_user_feedback(req.run_id, req.positive, req.comment)
        return {"status": "submitted", "run_id": req.run_id}
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/observability/eval-example")
async def add_eval_example(req: EvalExampleRequest):
    if not tracer.enabled:
        return {"status": "skipped", "reason": "LangSmith not enabled"}
    try:
        log_rag_example(req.query, req.answer, req.files_used)
        return {"status": "logged", "dataset": "copilot-analyst-eval"}
    except Exception as e:
        logger.error(f"Eval example error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
