"""
CDH Chat & Document Generation API
====================================
POST /api/cdh/chat              — CDH-aware chat (auto-selects analysis prompt)
POST /api/cdh/generate-document — Generates formal section-by-section reports
GET  /api/cdh/templates         — Lists available document templates
GET  /api/cdh/sources           — Shows which CDH sources are indexed
GET  /api/cdh/knowledge-articles— Lists indexed KB articles specifically
"""
import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.cdh.document_generator import CDHDocumentGenerator, DOCUMENT_SPECS
from app.cdh.orchestrator import CDHOrchestrator
from app.core.config import settings
from app.core.models import ChatRequest, StreamChunk

router = APIRouter()
logger = logging.getLogger(__name__)


class CDHChatRequest(ChatRequest):
    document_template: Optional[str] = None
    kb_only: bool = False       # retrieve only from knowledge articles
    data_only: bool = False     # retrieve only from data files


class DocumentRequest(BaseModel):
    question: str
    doc_type: str = "custom_analysis"
    llm_provider: Optional[str] = None
    session_id: Optional[str] = None


# ── Chat ──────────────────────────────────────────────────────────────────────

@router.post("/cdh/chat")
async def cdh_chat(request: Request, chat_req: CDHChatRequest):
    if not chat_req.session_id:
        chat_req.session_id = str(uuid.uuid4())

    rag_pipeline = request.app.state.rag_pipeline
    orchestrator = CDHOrchestrator(rag_pipeline)

    if chat_req.stream and settings.STREAMING_ENABLED:
        return StreamingResponse(
            _stream_chat(orchestrator, chat_req),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                     "X-Session-ID": chat_req.session_id},
        )

    full_text, structured, files, cdh_src, duration = "", [], [], [], 0
    async for chunk in orchestrator.stream_response(
        user_message=chat_req.message, history=chat_req.history,
        llm_provider=chat_req.llm_provider, session_id=chat_req.session_id,
        document_template=chat_req.document_template,
    ):
        if chunk.type == "text":       full_text += chunk.content or ""
        elif chunk.type == "structured": structured.append(chunk.data)
        elif chunk.type == "done":
            files    = chunk.data.get("files_analyzed", [])
            cdh_src  = chunk.data.get("cdh_sources", [])
            duration = chunk.data.get("duration_ms", 0)

    return {"session_id": chat_req.session_id, "message_id": str(uuid.uuid4()),
            "content": full_text, "structured_results": structured,
            "files_analyzed": files, "cdh_sources": cdh_src, "duration_ms": duration}


# ── Document generation ───────────────────────────────────────────────────────

@router.post("/cdh/generate-document")
async def generate_document(request: Request, doc_req: DocumentRequest):
    """
    Generate a full structured CDH analysis document, section by section.

    Available doc_types:
      nba_performance_report        — NBA strategy full report
      adm_health_report             — ADM model assessment
      segment_opportunity_report    — Value Finder opportunities
      channel_effectiveness_report  — Channel comparison
      kb_synthesis_report           — Synthesises knowledge articles
      custom_analysis               — Free-form question → doc
    """
    if doc_req.doc_type not in DOCUMENT_SPECS:
        return {"error": f"Unknown doc_type '{doc_req.doc_type}'",
                "available": list(DOCUMENT_SPECS.keys())}

    if not doc_req.session_id:
        doc_req.session_id = str(uuid.uuid4())

    rag_pipeline = request.app.state.rag_pipeline
    generator = CDHDocumentGenerator(rag_pipeline)

    return StreamingResponse(
        _stream_document(generator, doc_req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Doc-Type": doc_req.doc_type},
    )


# ── Catalog endpoints ─────────────────────────────────────────────────────────

@router.get("/cdh/templates")
async def list_templates():
    return {
        "templates": [
            {"doc_type": k, "title": v["title"],
             "description": v["description"],
             "sections": [s[1] for s in v["sections"]],
             "data_sources": v.get("data_sources", [])}
            for k, v in DOCUMENT_SPECS.items()
        ]
    }


@router.get("/cdh/sources")
async def list_cdh_sources(request: Request):
    from app.cdh.sources import CDH_SOURCES, detect_source
    rag_pipeline = request.app.state.rag_pipeline
    summaries = rag_pipeline.get_file_summaries()

    detected_data, detected_kb, unrecognised = {}, [], []

    for s in summaries:
        # Check data source
        data_src = detect_source(s["name"])
        if data_src:
            detected_data[data_src.source_id] = {
                "source_id": data_src.source_id,
                "display_name": data_src.display_name,
                "file": s["name"],
                "row_count": s.get("row_count"),
                "tags": data_src.tags,
            }
        elif s.get("file_type") in ("pdf","docx","html","md","kb_article",
                                    "cdh_config_guide","nba_strategy_doc",
                                    "adm_guide","pega_kb_article","data_dictionary",
                                    "release_notes","engagement_policy","general_doc"):
            detected_kb.append({"file": s["name"], "article_type": s.get("file_type"),
                                 "chunks": s.get("chunk_count", 0)})
        else:
            unrecognised.append(s["name"])

    return {
        "cdh_data_sources":    list(detected_data.values()),
        "knowledge_articles":  detected_kb,
        "unrecognised_files":  unrecognised,
        "total_indexed":       len(summaries),
        "known_data_types":    [s.display_name for s in CDH_SOURCES.values()],
    }


@router.get("/cdh/knowledge-articles")
async def list_knowledge_articles(request: Request):
    """List all indexed knowledge articles with their section counts and types."""
    rag_pipeline = request.app.state.rag_pipeline
    chunks = rag_pipeline._vector_store.get_chunks()

    articles: dict = {}
    for chunk in chunks:
        if chunk.metadata.get("is_kb_article"):
            fname = chunk.file_name
            if fname not in articles:
                articles[fname] = {
                    "filename":     fname,
                    "article_type": chunk.metadata.get("article_type", "document"),
                    "article_name": chunk.metadata.get("article_name", "Document"),
                    "tags":         chunk.metadata.get("tags", []),
                    "sections":     set(),
                    "chunk_count":  0,
                }
            articles[fname]["sections"].add(chunk.metadata.get("section", "General"))
            articles[fname]["chunk_count"] += 1

    result = []
    for a in articles.values():
        a["sections"] = sorted(a["sections"])
        result.append(a)

    return {
        "total_articles": len(result),
        "articles": sorted(result, key=lambda x: x["article_name"]),
    }


# ── Stream helpers ────────────────────────────────────────────────────────────

async def _stream_chat(orchestrator, req):
    try:
        async for chunk in orchestrator.stream_response(
            user_message=req.message, history=req.history,
            llm_provider=req.llm_provider, session_id=req.session_id,
            document_template=req.document_template,
        ):
            yield f"data: {json.dumps(chunk.model_dump())}\n\n".encode()
        yield b"data: [DONE]\n\n"
    except asyncio.CancelledError:
        yield b"data: [CANCELLED]\n\n"
    except Exception as e:
        logger.error(f"CDH chat stream error: {e}", exc_info=True)
        yield f"data: {json.dumps(StreamChunk(type='error', content=str(e)).model_dump())}\n\n".encode()
        yield b"data: [DONE]\n\n"


async def _stream_document(generator, req):
    try:
        async for chunk in generator.generate(
            question=req.question, doc_type=req.doc_type,
            llm_provider=req.llm_provider, session_id=req.session_id,
        ):
            yield f"data: {json.dumps(chunk.model_dump())}\n\n".encode()
        yield b"data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"Document generation error: {e}", exc_info=True)
        yield f"data: {json.dumps(StreamChunk(type='error', content=str(e)).model_dump())}\n\n".encode()
        yield b"data: [DONE]\n\n"
