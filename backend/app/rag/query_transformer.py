"""
Query transformation strategies:
  - Query Expansion : generate N alternative phrasings of the user query
  - HyDE            : generate a hypothetical answer, embed it, retrieve on that
Both improve recall for short/ambiguous queries significantly.
"""
import json
import logging
import re
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

EXPANSION_PROMPT = """You are a search query optimizer for a data analysis system.
Given a user question, generate {n} alternative search queries that capture
different aspects or phrasings. These will be used to retrieve relevant data chunks.

Output ONLY a JSON array of strings, e.g. ["query1", "query2", "query3"]
No explanation, no markdown fences.

User question: {question}"""

HYDE_PROMPT = """You are a data analyst. Write a 2-3 sentence hypothetical answer
to the following question as if you had already analyzed the relevant data files.
Be specific and use plausible numbers/values. This answer will be used for semantic search.

Question: {question}
Hypothetical answer:"""


class QueryTransformer:
    """
    Wraps query transformation calls. Requires an async LLM callable.
    Falls back gracefully on any error.
    """

    def __init__(self, llm_callable=None):
        """
        llm_callable: async fn(prompt: str) -> str
        If None, transformations are disabled.
        """
        self._llm = llm_callable

    async def expand(self, query: str, n: int = 3) -> List[str]:
        """Return [original] + [expanded queries]."""
        if not settings.QUERY_EXPANSION_ENABLED or self._llm is None:
            return [query]

        try:
            prompt = EXPANSION_PROMPT.format(n=n, question=query)
            raw = await self._llm(prompt)
            # Strip any accidental markdown fences
            clean = re.sub(r"```json|```", "", raw).strip()
            alternatives = json.loads(clean)
            if isinstance(alternatives, list):
                all_queries = [query] + [str(q) for q in alternatives if str(q) != query]
                logger.debug(f"Expanded '{query}' → {len(all_queries)} queries")
                return all_queries[:n + 1]
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
        return [query]

    async def hyde(self, query: str) -> Optional[str]:
        """Generate a hypothetical document to use as the search query."""
        if not settings.HYDE_ENABLED or self._llm is None:
            return None

        try:
            prompt = HYDE_PROMPT.format(question=query)
            hyp_doc = await self._llm(prompt)
            logger.debug(f"HyDE document generated ({len(hyp_doc)} chars)")
            return hyp_doc.strip()
        except Exception as e:
            logger.warning(f"HyDE failed: {e}")
            return None
