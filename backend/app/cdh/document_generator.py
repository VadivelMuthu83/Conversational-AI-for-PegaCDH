"""
CDH Document Generator
=======================
Produces fully-formatted analysis documents from RAG context.

Supported output formats:
  - streaming_markdown   : live-streamed Markdown (chat UI)
  - structured_json      : JSON with sections + tables for frontend rendering
  - document_export      : dict ready to pass to DOCX/PDF export

Supported document types:
  nba_performance_report
  adm_health_report
  segment_opportunity_report
  channel_effectiveness_report
  kb_synthesis_report     ← NEW: synthesises knowledge articles into analysis
  custom_analysis         ← free-form question → structured doc
"""
import json
import logging
import re
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.cdh.prompts import CDH_ANALYST_SYSTEM, get_document_prompt
from app.core.config import settings
from app.core.models import StreamChunk
from app.observability.langsmith_tracer import tracer
from app.observability.metrics import RAGMetrics
from app.rag.pipeline import RAGContext, RAGPipeline
from app.services.llm_provider import LLMMessage, get_llm_provider

logger = logging.getLogger(__name__)


# ─── Document section definitions ─────────────────────────────────────────────

DOCUMENT_SPECS: Dict[str, Dict] = {

    "nba_performance_report": {
        "title":       "NBA Strategy Performance Report",
        "description": "End-to-end performance analysis of Next Best Action strategy",
        "sections": [
            ("executive_summary",    "Executive Summary",
             "Summarise the overall NBA performance in 3-5 bullet points with key numbers."),
            ("action_performance",   "Action Performance by Channel",
             "Table of each action: impressions, accepts, rejects, accept_rate, avg_propensity."),
            ("weekly_trend",         "Weekly Trend Analysis",
             "Show week-over-week accept rate trend. Identify any sudden drops or spikes."),
            ("underperformers",      "Underperforming Actions",
             "List actions with accept_rate < 2%. Possible causes and recommendations."),
            ("underutilised",        "Underutilised Actions",
             "List actions with high propensity but low impression count."),
            ("adm_summary",          "ADM Model Health Summary",
             "Flag models with AUC < 0.6. List top 5 and bottom 5 models by AUC."),
            ("recommendations",      "Recommended Actions",
             "Numbered list of 4-6 specific, actionable recommendations prioritised by impact."),
        ],
        "data_sources": ["interaction_history", "adm_snapshot"],
    },

    "adm_health_report": {
        "title":       "ADM Model Health Assessment",
        "description": "Full assessment of all Adaptive Decision Manager models",
        "sections": [
            ("portfolio_overview",   "Model Portfolio Overview",
             "Total models, distribution of AUC scores, average response count."),
            ("auc_scorecard",        "AUC Performance Scorecard",
             "Table: model_name, channel, auc, response_count, status. Sort by AUC asc."),
            ("attention_needed",     "Models Requiring Immediate Attention",
             "Models with AUC < 0.6 or response_count < 200. Priority action for each."),
            ("predictor_analysis",   "Predictor Analysis",
             "Top predictors by importance across all models. Any unexpected/sensitive predictors."),
            ("champion_challenger",  "Champion / Challenger Results",
             "Compare champion vs challenger AUC delta. Which challengers should be promoted?"),
            ("remediation",          "Remediation Recommendations",
             "Specific steps to improve underperforming models."),
        ],
        "data_sources": ["adm_snapshot", "explainability_extract"],
    },

    "segment_opportunity_report": {
        "title":       "Customer Segment Opportunity Report",
        "description": "Value Finder analysis — revenue opportunities by segment",
        "sections": [
            ("segment_overview",     "Segment Overview",
             "Total segments, customers per quadrant (Underserved/Overserved/Balanced/Lost)."),
            ("underserved",          "Underserved Segments — Priority Opportunities",
             "Top 10 segments by opportunity value. Columns: segment, customers, gap, opp_value."),
            ("overserved",           "Overserved Segments — Cost Risk",
             "Segments with high engagement but low value. Cost of over-servicing."),
            ("revenue_summary",      "Revenue Opportunity Summary",
             "Total $ opportunity if underserved segments are engaged. Breakdown by channel."),
            ("recommendations",      "Recommended Campaign Actions",
             "For each top-5 underserved segment: recommended action + channel + expected lift."),
        ],
        "data_sources": ["value_finder", "interaction_history"],
    },

    "channel_effectiveness_report": {
        "title":       "Channel Effectiveness Report",
        "description": "Cross-channel NBA performance comparison and optimisation",
        "sections": [
            ("channel_summary",      "Channel Performance Summary",
             "Table: channel, impressions, accept_rate, avg_propensity, top_action."),
            ("action_channel_matrix","Action × Channel Matrix",
             "Heatmap-style table: rows=actions, cols=channels, values=accept_rate."),
            ("optimisation_gaps",    "Optimisation Opportunities",
             "Actions performing well in one channel but poorly in another."),
            ("recommendations",      "Recommendations",
             "Channel mix rebalancing recommendations with estimated impact."),
        ],
        "data_sources": ["interaction_history"],
    },

    "kb_synthesis_report": {
        "title":       "CDH Knowledge Synthesis Report",
        "description": "Analysis synthesised from Pega CDH knowledge articles and documentation",
        "sections": [
            ("key_findings",         "Key Findings from Documentation",
             "Summarise the most important points from the indexed knowledge articles."),
            ("configuration_notes",  "Configuration & Setup Notes",
             "Any configuration requirements, prerequisites, or constraints found."),
            ("best_practices",       "Best Practices & Recommendations",
             "Best practices mentioned in the documentation relevant to the question."),
            ("known_issues",         "Known Issues & Workarounds",
             "Any issues, limitations, or workarounds documented in the KB articles."),
            ("action_plan",          "Implementation Action Plan",
             "Step-by-step action plan based on the documentation."),
        ],
        "data_sources": ["pega_kb_article", "cdh_config_guide", "nba_strategy_doc", "adm_guide"],
    },

    "custom_analysis": {
        "title":       "CDH Custom Analysis",
        "description": "Custom analysis based on your specific question",
        "sections": [
            ("summary",   "Analysis Summary",    "Answer the question with key findings."),
            ("details",   "Detailed Findings",   "Detailed breakdown with tables and metrics."),
            ("insights",  "Key Insights",        "3-5 non-obvious insights from the data."),
            ("next_steps","Next Steps",          "Recommended actions with owner and timeline."),
        ],
        "data_sources": [],  # all sources
    },
}


# ─── Document Generator ───────────────────────────────────────────────────────

class CDHDocumentGenerator:
    """
    Generates structured analysis documents section by section,
    streaming each section as it completes.
    """

    def __init__(self, rag_pipeline: RAGPipeline):
        self._rag = rag_pipeline

    async def generate(
        self,
        question: str,
        doc_type: str = "custom_analysis",
        llm_provider: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Generate a full document section by section.
        Yields StreamChunks — compatible with the chat SSE stream.
        """
        sid = session_id or str(uuid.uuid4())
        spec = DOCUMENT_SPECS.get(doc_type, DOCUMENT_SPECS["custom_analysis"])
        llm  = get_llm_provider(llm_provider or settings.LLM_PROVIDER)

        metrics = RAGMetrics(session_id=sid, query=question,
                             llm_provider=llm_provider or settings.LLM_PROVIDER)
        metrics.run_id = tracer.start_run(
            name=f"cdh_doc_{doc_type}",
            run_type="chain",
            inputs={"question": question, "doc_type": doc_type},
            tags=[doc_type, "document_generation"],
        )

        # ── Yield document header ────────────────────────────────────────────
        yield StreamChunk(type="status", content=f"📄 Generating: {spec['title']}…")
        yield StreamChunk(type="text", content=f"# {spec['title']}\n\n")
        yield StreamChunk(type="text",
                          content=f"*Generated by Copilot Analyst — Pega CDH Expert*\n\n---\n\n")

        # ── Retrieve context once for all sections ────────────────────────────
        yield StreamChunk(type="status", content="🔍 Retrieving CDH knowledge…")
        metrics.begin_step("retrieve")

        retrieval_queries = self._build_retrieval_queries(question, spec)
        all_contexts = []
        for q in retrieval_queries:
            ctx = await self._rag.retrieve(q)
            all_contexts.append(ctx)

        merged = self._merge_contexts(all_contexts)
        metrics.end_step()
        metrics.log_retrieval_step(
            queries=retrieval_queries,
            chunks_retrieved=len(merged.chunks),
            files_used=merged.files_used,
            retrieval_mode=settings.RETRIEVAL_MODE,
            retrieval_ms=sum(c.retrieval_ms for c in all_contexts),
        )

        # Identify article types in context
        kb_sources = self._identify_sources(merged)
        yield StreamChunk(type="status",
                          content=f"📚 Sources: {', '.join(kb_sources) or 'indexed files'}…")

        # ── Generate each section ────────────────────────────────────────────
        full_document = f"# {spec['title']}\n\n"
        section_jsons = []

        for section_id, section_title, section_instruction in spec["sections"]:
            yield StreamChunk(type="status",
                              content=f"✍️  Writing: {section_title}…")
            yield StreamChunk(type="text", content=f"\n## {section_title}\n\n")

            section_prompt = self._build_section_prompt(
                question=question,
                section_title=section_title,
                section_instruction=section_instruction,
                doc_title=spec["title"],
                context=merged.text,
            )

            section_text = ""
            metrics.begin_step(section_id)

            async for token in llm.stream_chat(
                [LLMMessage(role="user", content=section_prompt)],
                system=CDH_ANALYST_SYSTEM,
            ):
                section_text += token
                yield StreamChunk(type="text", content=token)

            metrics.end_step()
            full_document += f"\n## {section_title}\n\n{section_text}\n"

            # Extract any JSON table from this section
            json_block = self._extract_json(section_text, merged.files_used)
            if json_block:
                json_block["section"] = section_title
                section_jsons.append(json_block)
                yield StreamChunk(type="structured", data=json_block)

            yield StreamChunk(type="text", content="\n\n---\n\n")

        # ── Final metadata block ─────────────────────────────────────────────
        yield StreamChunk(type="text",
                          content=f"\n\n*Sources: {', '.join(merged.files_used)}*\n")

        run_id = metrics.log_to_langsmith(full_document)
        yield StreamChunk(
            type="done",
            data={
                "doc_type":        doc_type,
                "doc_title":       spec["title"],
                "files_analyzed":  merged.files_used,
                "sources_used":    kb_sources,
                "sections_count":  len(spec["sections"]),
                "structured_tables": len(section_jsons),
                "langsmith_run_id": run_id,
            },
        )

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _build_retrieval_queries(self, question: str, spec: Dict) -> List[str]:
        queries = [question]
        for _, title, instruction in spec["sections"]:
            queries.append(f"{title}: {question}")
        # Add source-specific queries
        for src in spec.get("data_sources", []):
            queries.append(f"{src} {question}")
        return list(dict.fromkeys(queries))[:6]

    def _build_section_prompt(
        self, question: str, section_title: str,
        section_instruction: str, doc_title: str, context: str
    ) -> str:
        return (
            f"You are generating section '{section_title}' of a '{doc_title}' report.\n\n"
            f"Original question: {question}\n\n"
            f"Section instruction: {section_instruction}\n\n"
            f"Use ONLY information from the retrieved context below.\n"
            f"If the context does not contain enough data for this section, "
            f"clearly state 'Insufficient data available for this section.'\n\n"
            f"Include a Markdown table where appropriate.\n"
            f"If you have a structured result, include a ```json block.\n\n"
            f"Retrieved Context:\n{context}\n\n"
            f"Write the '{section_title}' section now:"
        )

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
        chunks = chunks[:settings.TOP_K_RERANK * 2]   # more context for docs
        text = "\n\n---\n\n".join(
            f"[{r.chunk.metadata.get('article_type', r.chunk.file_type)} | "
            f"{r.chunk.file_name}"
            + (f" | {r.chunk.metadata.get('section', '')}" if r.chunk.metadata.get("section") else "")
            + f"]\n{r.chunk.text}"
            for r in chunks
        )
        return RC(text=text or "No context found.",
                  chunks=chunks, files_used=list(files),
                  queries_used=list(dict.fromkeys(queries)),
                  retrieval_ms=sum(c.retrieval_ms for c in contexts))

    def _identify_sources(self, context: RAGContext) -> List[str]:
        sources = set()
        for r in context.chunks:
            art_name = r.chunk.metadata.get("article_name")
            art_type = r.chunk.metadata.get("article_type")
            if art_name:
                sources.add(art_name)
            elif art_type:
                sources.add(art_type)
            elif r.chunk.file_type:
                sources.add(r.chunk.file_type)
        return sorted(sources)

    def _extract_json(self, text: str, files_used: List[str]) -> Optional[Dict]:
        matches = re.findall(r"```json\s*([\s\S]*?)```", text)
        if not matches:
            return None
        try:
            data = json.loads(matches[-1])
            if not data.get("files_used"):
                data["files_used"] = files_used
            return data
        except Exception:
            return None
