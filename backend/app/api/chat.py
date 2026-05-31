"""
Chat API: uses AgentOrchestrator v2 (RAG + LangSmith).
Attaches langsmith_run_id to response header for feedback loop.
"""
import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.agents.orchestrator import AgentOrchestrator
from app.core.config import settings
from app.core.models import ChatRequest, ChatResponse, StreamChunk

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat")
async def chat(request: Request, chat_req: ChatRequest):
    if not chat_req.session_id:
        chat_req.session_id = str(uuid.uuid4())

    rag_pipeline = request.app.state.rag_pipeline
    orchestrator = AgentOrchestrator(rag_pipeline)

    if chat_req.stream and settings.STREAMING_ENABLED:
        return StreamingResponse(
            _stream_generator(orchestrator, chat_req),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Session-ID": chat_req.session_id,
            },
        )

    # Sync mode
    full_text = ""
    structured_results = []
    files_analyzed = []
    duration_ms = 0
    langsmith_run_id = None

    async for chunk in orchestrator.stream_response(
        user_message=chat_req.message,
        history=chat_req.history,
        llm_provider=chat_req.llm_provider,
        session_id=chat_req.session_id,
    ):
        if chunk.type == "text":
            full_text += chunk.content or ""
        elif chunk.type == "structured" and chunk.data:
            structured_results.append(chunk.data)
        elif chunk.type == "done" and chunk.data:
            files_analyzed = chunk.data.get("files_analyzed", [])
            duration_ms = chunk.data.get("duration_ms", 0)
            langsmith_run_id = chunk.data.get("langsmith_run_id")

    resp = ChatResponse(
        session_id=chat_req.session_id,
        message_id=str(uuid.uuid4()),
        content=full_text,
        structured_results=structured_results,
        files_analyzed=files_analyzed,
        duration_ms=duration_ms,
    )
    return resp


async def _stream_generator(orchestrator, chat_req):
    try:
        async for chunk in orchestrator.stream_response(
            user_message=chat_req.message,
            history=chat_req.history,
            llm_provider=chat_req.llm_provider,
            session_id=chat_req.session_id,
        ):
            data = chunk.model_dump()
            yield f"data: {json.dumps(data)}\n\n".encode()
        yield b"data: [DONE]\n\n"
    except asyncio.CancelledError:
        yield b"data: [CANCELLED]\n\n"
    except Exception as e:
        logger.error(f"Stream error: {e}", exc_info=True)
        error_chunk = StreamChunk(type="error", content=str(e))
        yield f"data: {json.dumps(error_chunk.model_dump())}\n\n".encode()
        yield b"data: [DONE]\n\n"
