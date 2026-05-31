"""
CDH Document Generator
=======================
Generates structured analysis documents from RAG retrieval results.

Supports:
  - NBA Performance Report
  - ADM Model Health Report
  - Segment Opportunity Report
  - Channel Effectiveness Report
  - Ad-hoc analysis (any question)

Output formats:
  - Streaming Markdown (default — for chat UI)
  - Structured JSON (for frontend table rendering)
  - Document dict (for export to PDF/DOCX)
"""
import asyncio
import json
import logging
import re
import time
import uuid
from typing import AsyncGenerator, Dict, List, Optional

from app.cdh.prompts import (
    CDH_ANALYST_SYSTEM,
    get_document_prompt,
    route_analysis_prompt,
)
from app.core.config import settings
from app.core.models import Message, StreamChunk
from app.observability.metrics import RAGMetrics
from app.observability.langsmith_tracer import tracer
from app.rag.pipeline import RAGContext, RAGPipeline
from app.services.llm_provider import LLMMessage, get_llm_provider

logger = logging.getLogger(__name__)


class CDHOrchestrator:
    """
    CDH-aware orchestrator — replaces the generic AgentOrchestrator
    when CDH data sources are detected.

    Differences from generic orchestrator:
    1. Uses CDH_ANALYST_SYSTEM prompt (knows all 5 CDH sources)
    2. Routes to source-specific analysis prompts
    3. Supports document generation mode
    4. Tags retrieval by CDH source type
    5. Generates Pega-specific structured outputs
    """

    def __init__(self, rag_pipeline: RAGPipeline):
        self._rag = rag_pipeline

    async def stream_response(
        self,
        user_message: str,
        history: List[Message],
        llm_provider: Optional[str] = None,
        session_id: Optional[str] = None,
        document_template: Optional[str] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Full CDH-aware RAG → LLM pipeline with streaming output.
        document_template: if set, generates a formal report document.
        """
        sid = session_id or str(uuid.uuid4())
        provider_name = llm_provider or settings.LLM_PROVIDER
        llm = get_llm_provider(provider_name)

        metrics = RAGMetrics(session_id=sid, query=user_message, llm_provider=provider_name)
        metrics.run_id = tracer.start_run(
            name="cdh_analysis",
            run_type="chain",
            inputs={"query": user_message, "session_id": sid},
            tags=[provider_name, "cdh", settings.RETRIEVAL_MODE],
        )

        # ── Step 1: Route to analysis type ──────────────────────────────────
        analysis_prompt = route_analysis_prompt(user_message)
        yield StreamChunk(type="status", content="🔍 Identifying CDH analysis type…")

        # ── Step 2: Build retrieval queries ─────────────────────────────────
        queries = await self._build_cdh_queries(user_message, llm)
        yield StreamChunk(
            type="status",
            content=f"📊 Retrieving from {len(queries)} CDH data source queries…"
        )

        # ── Step 3: Retrieve ─────────────────────────────────────────────────
        metrics.begin_step("retrieve")
        all_contexts: List[RAGContext] = []
        for q in queries:
            ctx = await self._rag.retrieve(q, top_k=settings.TOP_K_RETRIEVAL)
            all_contexts.append(ctx)
        merged = self._merge_contexts(all_contexts)
        metrics.end_step()
        metrics.log_retrieval_step(
            queries=queries,
            chunks_retrieved=len(merged.chunks),
            files_used=merged.files_used,
            retrieval_mode=settings.RETRIEVAL_MODE,
            retrieval_ms=sum(c.retrieval_ms for c in all_contexts),
        )

        cdh_sources_found = self._identify_cdh_sources(merged)
        yield StreamChunk(
            type="status",
            content=f"🧠 Analysing {len(merged.files_used)} file(s) "
                    f"[{', '.join(cdh_sources_found)}]…"
        )

        # ── Step 4: Build the full prompt ────────────────────────────────────
        if document_template:
            final_question = get_document_prompt(document_template, user_message)
        else:
            final_question = f"{analysis_prompt}\n\nQuestion: {user_message}"

        messages = self._build_messages(final_question, history, merged)

        # ── Step 5: Stream LLM answer ────────────────────────────────────────
        metrics.begin_step("synthesize")
        full_response = ""
        llm_start = time.time()

        async for token in llm.stream_chat(messages, system=CDH_ANALYST_SYSTEM):
            full_response += token
            yield StreamChunk(type="text", content=token)

        llm_ms = int((time.time() - llm_start) * 1000)
        metrics.end_step(llm_ms=llm_ms)
        metrics.log_llm_step(
            prompt_preview=messages[-1].content[:300] if messages else "",
            output_preview=full_response[:300],
            tokens_estimate=len(full_response) // 4,
            llm_ms=llm_ms,
        )

        # ── Step 6: Extract structured results ───────────────────────────────
        structured = self._extract_structured(full_response, merged.files_used)
        if structured:
            metrics.structured_results = 1
            yield StreamChunk(type="structured", data=structured)

        # ── Step 7: Done ──────────────────────────────────────────────────────
        run_id = metrics.log_to_langsmith(full_response)
        yield StreamChunk(
            type="done",
            data={
                "files_analyzed":    merged.files_used,
                "cdh_sources":       cdh_sources_found,
                "chunks_retrieved":  len(merged.chunks),
                "queries_used":      merged.queries_used,
                "retrieval_mode":    settings.RETRIEVAL_MODE,
                "duration_ms":       llm_ms,
                "langsmith_run_id":  run_id,
                "document_template": document_template,
            }
        )

    # ─── CDH-specific query building ──────────────────────────────────────────

    async def _build_cdh_queries(self, user_question: str, llm) -> List[str]:
        """
        Generate CDH-aware retrieval queries.
        Adds source-specific query variants beyond generic expansion.
        """
        base_queries = [user_question]

        # Add source-specific retrieval queries based on keywords
        q_lower = user_question.lower()

        if any(kw in q_lower for kw in ["performance", "accept", "action", "nba", "strategy"]):
            base_queries.extend([
                "NBA action accept rate impressions rejects by channel",
                "interaction history outcome propensity priority",
            ])

        if any(kw in q_lower for kw in ["auc", "model", "adm", "train", "predict"]):
            base_queries.extend([
                "ADM model AUC performance score response count",
                "adaptive model snapshot predictor importance",
            ])

        if any(kw in q_lower for kw in ["segment", "value", "engagement", "underserved"]):
            base_queries.extend([
                "value finder segment engagement gap opportunity",
                "customer segment quadrant underserved overserved",
            ])

        if any(kw in q_lower for kw in ["explain", "why", "predictor", "fairness"]):
            base_queries.extend([
                "explainability predictor weight contribution direction",
                "model decision explanation feature importance",
            ])

        if any(kw in q_lower for kw in ["channel", "email", "web", "mobile"]):
            base_queries.extend([
                "channel effectiveness accept rate impressions comparison",
            ])

        # Deduplicate
        return list(dict.fromkeys(base_queries))[:6]

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _identify_cdh_sources(self, context: RAGContext) -> List[str]:
        """Extract CDH source names from retrieved chunk metadata."""
        sources = set()
        for r in context.chunks:
            cdh_id = r.chunk.metadata.get("cdh_source_id")
            cdh_name = r.chunk.metadata.get("cdh_source_name")
            if cdh_name:
                sources.add(cdh_name)
            elif cdh_id:
                sources.add(cdh_id)
        return sorted(sources) if sources else ["General knowledge"]

    def _merge_contexts(self, contexts: List[RAGContext]) -> RAGContext:
        from app.rag.pipeline import RAGContext as RC
        seen_ids = set()
        merged_chunks, all_files, all_queries = [], set(), []
        for ctx in contexts:
            all_files.update(ctx.files_used)
            all_queries.extend(ctx.queries_used)
            for r in ctx.chunks:
                if r.chunk.id not in seen_ids:
                    seen_ids.add(r.chunk.id)
                    merged_chunks.append(r)
        merged_chunks.sort(key=lambda r: r.score, reverse=True)
        merged_chunks = merged_chunks[:settings.TOP_K_RERANK]
        ctx_text = "\n\n---\n\n".join(
            f"[SOURCE: {r.chunk.file_name} | CDH: {r.chunk.metadata.get('cdh_source_name', 'Unknown')}]\n{r.chunk.text}"
            for r in merged_chunks
        )
        return RC(
            text=ctx_text or "No relevant CDH data found.",
            chunks=merged_chunks,
            files_used=list(all_files),
            queries_used=list(dict.fromkeys(all_queries)),
            retrieval_ms=sum(c.retrieval_ms for c in contexts),
        )

    def _build_messages(
        self, question: str, history: List[Message], context: RAGContext
    ) -> List[LLMMessage]:
        messages = []
        for msg in history[-6:]:
            messages.append(LLMMessage(role=msg.role, content=msg.content))

        file_list = "\n".join(f"  - {f}" for f in context.files_used)
        user_turn = (
            f"## Files Indexed\n{file_list or 'None'}\n\n"
            f"## Retrieved CDH Data\n{context.text}\n\n"
            f"## Analysis Request\n{question}"
        )
        messages.append(LLMMessage(role="user", content=user_turn))
        return messages

    def _extract_structured(self, response_text: str, files_used: List[str]) -> Optional[Dict]:
        matches = re.findall(r"```json\s*([\s\S]*?)```", response_text)
        if not matches:
            return None
        try:
            data = json.loads(matches[-1])
            if not data.get("files_used"):
                data["files_used"] = files_used
            return data
        except Exception:
            return None
