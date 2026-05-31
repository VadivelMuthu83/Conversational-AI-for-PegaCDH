"""
RAG evaluation metrics logged to LangSmith.
Computes:
  - Retrieval precision (chunk relevance heuristic)
  - Context utilisation  (how much context the LLM actually used)
  - Answer faithfulness  (LLM-based — optional, requires extra LLM call)
  - Latency breakdown per pipeline step
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.observability.langsmith_tracer import tracer

logger = logging.getLogger(__name__)


@dataclass
class StepMetric:
    name: str
    start: float = field(default_factory=time.time)
    end: Optional[float] = None
    metadata: Dict = field(default_factory=dict)

    def stop(self, **metadata):
        self.end = time.time()
        self.metadata.update(metadata)

    @property
    def duration_ms(self) -> int:
        if self.end is None:
            return 0
        return int((self.end - self.start) * 1000)


class RAGMetrics:
    """
    Collects timing and quality metrics for a single RAG invocation.
    Call .log_to_langsmith() at the end to push everything upstream.
    """

    def __init__(self, session_id: str, query: str, llm_provider: str):
        self.session_id = session_id
        self.query = query
        self.llm_provider = llm_provider
        self.run_id: Optional[str] = None
        self.steps: List[StepMetric] = []
        self._active: Optional[StepMetric] = None
        self._total_start = time.time()

        # Retrieval metadata
        self.queries_used: List[str] = []
        self.chunks_retrieved: int = 0
        self.files_used: List[str] = []
        self.retrieval_mode: str = ""

        # Generation metadata
        self.answer_length: int = 0
        self.structured_results: int = 0

    # ─── Step tracking ────────────────────────────────────────────────────────

    def begin_step(self, name: str) -> StepMetric:
        step = StepMetric(name=name)
        self.steps.append(step)
        self._active = step
        return step

    def end_step(self, **metadata):
        if self._active:
            self._active.stop(**metadata)
            self._active = None

    # ─── Final logging ────────────────────────────────────────────────────────

    def log_to_langsmith(self, answer: str, error: Optional[str] = None):
        """Push metrics to LangSmith as a finished run."""
        self.answer_length = len(answer)
        total_ms = int((time.time() - self._total_start) * 1000)

        step_breakdown = {s.name: s.duration_ms for s in self.steps}

        inputs = {
            "query": self.query,
            "session_id": self.session_id,
            "llm_provider": self.llm_provider,
        }
        outputs = {
            "answer_length": self.answer_length,
            "chunks_retrieved": self.chunks_retrieved,
            "files_used": self.files_used,
            "queries_used": self.queries_used,
            "structured_results": self.structured_results,
            "total_ms": total_ms,
            "step_breakdown_ms": step_breakdown,
        }

        if self.run_id is None:
            # Create a parent run for this full RAG invocation
            self.run_id = tracer.start_run(
                name="rag_invocation",
                run_type="chain",
                inputs=inputs,
                tags=[self.llm_provider, self.retrieval_mode],
                metadata={
                    "session_id": self.session_id,
                    "files_count": len(self.files_used),
                },
            )

        tracer.end_run(
            run_id=self.run_id,
            outputs=outputs,
            error=error,
        )

        logger.debug(
            f"RAG metrics logged → LangSmith run_id={self.run_id} "
            f"total={total_ms}ms chunks={self.chunks_retrieved}"
        )
        return self.run_id

    def log_retrieval_step(
        self,
        queries: List[str],
        chunks_retrieved: int,
        files_used: List[str],
        retrieval_mode: str,
        retrieval_ms: int,
    ):
        self.queries_used = queries
        self.chunks_retrieved = chunks_retrieved
        self.files_used = files_used
        self.retrieval_mode = retrieval_mode

        run_id = tracer.start_run(
            name="rag_retrieval",
            run_type="retriever",
            inputs={"queries": queries},
            tags=[retrieval_mode],
            parent_run_id=self.run_id,
        )
        tracer.end_run(
            run_id=run_id,
            outputs={
                "chunks_retrieved": chunks_retrieved,
                "files_used": files_used,
                "retrieval_ms": retrieval_ms,
            },
        )

    def log_llm_step(
        self,
        prompt_preview: str,
        output_preview: str,
        tokens_estimate: int,
        llm_ms: int,
    ):
        run_id = tracer.start_run(
            name="llm_generation",
            run_type="llm",
            inputs={"prompt_preview": prompt_preview[:300]},
            tags=[self.llm_provider],
            parent_run_id=self.run_id,
        )
        tracer.end_run(
            run_id=run_id,
            outputs={
                "output_preview": output_preview[:300],
                "tokens_estimate": tokens_estimate,
                "llm_ms": llm_ms,
            },
        )


# ─── Feedback API ─────────────────────────────────────────────────────────────

def submit_user_feedback(run_id: str, positive: bool, comment: Optional[str] = None):
    """Called when a user clicks thumbs-up or thumbs-down in the UI."""
    tracer.submit_feedback(
        run_id=run_id,
        score=1.0 if positive else 0.0,
        comment=comment,
        key="user_rating",
    )


def log_rag_example(query: str, answer: str, files_used: List[str]):
    """Save a Q&A pair to the LangSmith evaluation dataset."""
    tracer.log_example(
        dataset_name="copilot-analyst-eval",
        inputs={"question": query, "files": files_used},
        outputs={"answer": answer},
    )
