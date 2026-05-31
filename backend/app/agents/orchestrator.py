"""
Agent Orchestrator — Plan → Retrieve → Synthesize.
Robust JSON parsing handles Gemini / OpenAI / Anthropic response formats.
"""
import json
import logging
import re
import time
import uuid
from typing import AsyncGenerator, Dict, List, Optional

from app.core.config import settings
from app.core.models import Message, StreamChunk
from app.observability.langsmith_tracer import tracer
from app.observability.metrics import RAGMetrics
from app.rag.pipeline import RAGContext, RAGPipeline
from app.services.llm_provider import LLMMessage, get_llm_provider

logger = logging.getLogger(__name__)


ANALYST_SYSTEM = """You are Copilot Analyst — an expert data analyst and Pega CDH specialist.

You receive retrieved context (data files + Pega CDH knowledge articles) and a user question.
Always respond with:
1. A clear direct answer to the question
2. Key findings with specific numbers or facts from the context
3. A Markdown table where the data supports it
4. Actionable recommendations

Reference the source files you used. Be concise and precise."""


# NOTE: Use a plain function to build the planner prompt — NOT str.format().
# str.format() crashes when the template contains JSON curly braces like {"key": "value"}.
def _build_planner_prompt(question: str, files: str) -> str:
    return (
        "You are a query planner. Given a question and file list, "
        "output ONLY a JSON object with no markdown fences and no explanation.\n"
        "Required format: "
        '{"search_queries": ["query1", "query2"], "analysis_type": "general"}\n\n'
        f"Question: {question}\n"
        f"Files available: {files}"
    )


def _extract_json(text: str) -> Optional[Dict]:
    """
    Extract the first valid JSON object from LLM output.
    Handles markdown fences, extra prose, and raw JSON.
    """
    if not text or not text.strip():
        return None

    # Pattern 1: ```json ... ```
    m = re.search(r"```json\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass

    # Pattern 2: ``` ... ```
    m = re.search(r"```\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass

    # Pattern 3: first { ... } block in the text
    m = re.search(r"\{[\s\S]*?\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass

    # Pattern 4: greedy { ... } (for nested objects)
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass

    # Pattern 5: entire text is JSON
    try:
        return json.loads(text.strip())
    except Exception:
        pass

    return None


class AgentOrchestrator:
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

        sid           = session_id or str(uuid.uuid4())
        provider_name = llm_provider or settings.LLM_PROVIDER
        llm           = get_llm_provider(provider_name)

        metrics = RAGMetrics(
            session_id=sid,
            query=user_message,
            llm_provider=provider_name,
        )
        metrics.run_id = tracer.start_run(
            name="copilot_analyst_chat",
            run_type="chain",
            inputs={"query": user_message},
            tags=[provider_name, settings.RETRIEVAL_MODE],
        )

        # ── Step 1: Plan ───────────────────────────────────────────────────
        yield StreamChunk(type="status", content="Analysing your question…")
        metrics.begin_step("plan")
        plan = await self._plan(user_message, llm)
        metrics.end_step()

        # ── Step 2: Retrieve ───────────────────────────────────────────────
        queries = plan.get("search_queries", [user_message])
        if not queries:
            queries = [user_message]

        yield StreamChunk(
            type="status",
            content=f"Searching {len(queries)} quer{'ies' if len(queries) != 1 else 'y'} across indexed files…",
        )
        metrics.begin_step("retrieve")

        all_contexts: List[RAGContext] = []
        for q in queries[:4]:          # cap at 4 to avoid excessive calls
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

        yield StreamChunk(
            type="status",
            content=f"Generating answer from {len(merged.files_used)} source(s)…",
        )

        # ── Step 3: Synthesize ─────────────────────────────────────────────
        messages  = self._build_messages(user_message, history, merged)
        full_text = ""
        llm_start = time.time()
        metrics.begin_step("synthesize")

        async for token in llm.stream_chat(messages, system=ANALYST_SYSTEM):
            full_text += token
            yield StreamChunk(type="text", content=token)

        llm_ms = int((time.time() - llm_start) * 1000)
        metrics.end_step(llm_ms=llm_ms)
        metrics.log_llm_step(
            prompt_preview=messages[-1].content[:200] if messages else "",
            output_preview=full_text[:200],
            tokens_estimate=len(full_text) // 4,
            llm_ms=llm_ms,
        )

        # ── Step 4: Extract structured data ────────────────────────────────
        structured = _extract_json(full_text)
        if (structured and isinstance(structured, dict)
                and structured.get("type") in ("table", "chart", "summary")):
            if not structured.get("files_used"):
                structured["files_used"] = merged.files_used
            yield StreamChunk(type="structured", data=structured)

        # ── Step 5: Done ───────────────────────────────────────────────────
        run_id = metrics.log_to_langsmith(full_text)
        yield StreamChunk(
            type="done",
            data={
                "files_analyzed":   merged.files_used,
                "chunks_retrieved": len(merged.chunks),
                "queries_used":     merged.queries_used,
                "retrieval_mode":   settings.RETRIEVAL_MODE,
                "duration_ms":      llm_ms,
                "langsmith_run_id": run_id,
            },
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _plan(self, query: str, llm) -> Dict:
        """
        Ask the LLM to suggest search queries for this question.
        Falls back to [query] on any error — the app always works.
        """
        default = {"search_queries": [query], "analysis_type": "general"}

        file_summary = self._build_file_summary()
        if not file_summary:
            return default

        prompt_text = _build_planner_prompt(
            question=query,
            files=file_summary[:400],
        )

        try:
            raw = await llm.chat([LLMMessage(role="user", content=prompt_text)])
            result = _extract_json(raw)
            if (result
                    and isinstance(result, dict)
                    and isinstance(result.get("search_queries"), list)
                    and result["search_queries"]):
                logger.debug(f"Plan: {result}")
                return result
            logger.debug(f"Planner returned non-JSON or missing key: {raw[:120]}")
        except Exception as e:
            logger.warning(f"Planner failed ({e}); using default plan")

        return default

    def _merge_contexts(self, contexts: List[RAGContext]) -> RAGContext:
        from app.rag.pipeline import RAGContext as RC
        seen, chunks, files, queries = set(), [], set(), []
        for ctx in contexts:
            files.update(ctx.files_used)
            queries.extend(ctx.queries_used)
            for r in ctx.chunks:
                if r.chunk.id not in seen:
                    seen.add(r.chunk.id)
                    chunks.append(r)
        chunks.sort(key=lambda r: r.score, reverse=True)
        chunks = chunks[:settings.TOP_K_RERANK * 2]
        text = "\n\n---\n\n".join(
            f"[Source: {r.chunk.file_name}]\n{r.chunk.text}"
            for r in chunks
        )
        return RC(
            text=text or "No relevant context found.",
            chunks=chunks,
            files_used=list(files),
            queries_used=list(dict.fromkeys(queries)),
            retrieval_ms=sum(c.retrieval_ms for c in contexts),
        )

    def _build_file_summary(self) -> str:
        summaries = self._rag.get_file_summaries()
        if not summaries:
            return ""
        lines = []
        for s in summaries[:12]:
            line = f"- {s['name']}"
            if s.get("row_count"):
                line += f" ({s['row_count']} rows)"
            elif s.get("summary"):
                line += f" ({s['summary'][:40]})"
            lines.append(line)
        return "\n".join(lines)

    def _build_messages(
        self,
        question: str,
        history: List[Message],
        context: RAGContext,
    ) -> List[LLMMessage]:
        messages = []

        # Include last 4 turns of conversation history
        for msg in history[-4:]:
            messages.append(LLMMessage(role=msg.role, content=msg.content))

        file_list = "\n".join(f"  - {f}" for f in context.files_used) or "  (none)"
        user_turn = (
            f"Sources used:\n{file_list}\n\n"
            f"Retrieved context:\n{context.text}\n\n"
            f"Question: {question}"
        )
        messages.append(LLMMessage(role="user", content=user_turn))
        return messages
