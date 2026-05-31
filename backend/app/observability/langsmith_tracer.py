"""
LangSmith observability — compatible with langsmith 0.8.x.
Accepts LANGSMITH_* or LANGCHAIN_* env var names.
Fully no-op when disabled or package unavailable.
"""
import functools
import logging
import os
import time
import uuid
from typing import Callable, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _configure() -> bool:
    if not settings.tracing_enabled:
        return False
    if not settings.langsmith_api_key:
        logger.warning("LangSmith enabled but no API key — set LANGSMITH_API_KEY")
        return False
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"]    = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"]    = settings.langsmith_project
    os.environ["LANGCHAIN_ENDPOINT"]   = settings.langsmith_endpoint
    logger.info(f"LangSmith tracing → project='{settings.langsmith_project}'")
    return True


LANGSMITH_ENABLED = _configure()


class LangSmithTracer:
    def __init__(self):
        self._client  = None
        self._enabled = LANGSMITH_ENABLED
        if self._enabled:
            try:
                from langsmith import Client
                self._client = Client(
                    api_key=settings.langsmith_api_key,
                    api_url=settings.langsmith_endpoint,
                )
                logger.info("LangSmith client ready")
            except ImportError:
                logger.warning("langsmith not installed — tracing disabled")
                self._enabled = False
            except Exception as e:
                logger.warning(f"LangSmith init failed: {e}")
                self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start_run(self, name: str, run_type: str = "chain",
                  inputs: Optional[Dict] = None, tags: Optional[List[str]] = None,
                  metadata: Optional[Dict] = None,
                  parent_run_id: Optional[str] = None) -> Optional[str]:
        if not self._enabled or not self._client:
            return None
        try:
            run_id = str(uuid.uuid4())
            # langsmith 0.8.x uses client.create_run
            self._client.create_run(
                id=run_id, name=name, run_type=run_type,
                inputs=inputs or {}, tags=tags or [],
                extra={"metadata": metadata or {}},
                parent_run_id=parent_run_id,
            )
            return run_id
        except Exception as e:
            logger.debug(f"LangSmith start_run: {e}")
            return None

    def end_run(self, run_id: Optional[str], outputs: Optional[Dict] = None,
                error: Optional[str] = None):
        if not self._enabled or not self._client or not run_id:
            return
        try:
            self._client.update_run(run_id=run_id, outputs=outputs or {},
                                    error=error)
        except Exception as e:
            logger.debug(f"LangSmith end_run: {e}")

    def submit_feedback(self, run_id: str, score: float,
                        comment: Optional[str] = None, key: str = "user_rating"):
        if not self._enabled or not self._client:
            return
        try:
            self._client.create_feedback(run_id=run_id, key=key,
                                         score=score, comment=comment or "")
        except Exception as e:
            logger.debug(f"LangSmith feedback: {e}")

    def log_example(self, dataset_name: str, inputs: Dict,
                    outputs: Dict, metadata: Optional[Dict] = None):
        if not self._enabled or not self._client:
            return
        try:
            datasets = list(self._client.list_datasets(dataset_name=dataset_name))
            dataset  = datasets[0] if datasets else self._client.create_dataset(
                dataset_name=dataset_name,
                description=f"Eval dataset for {settings.langsmith_project}",
            )
            self._client.create_example(inputs=inputs, outputs=outputs,
                                        metadata=metadata or {},
                                        dataset_id=dataset.id)
        except Exception as e:
            logger.debug(f"LangSmith log_example: {e}")

    def trace(self, name: str, run_type: str = "chain",
              tags: Optional[List[str]] = None,
              capture_input: bool = True, capture_output: bool = True):
        def decorator(func: Callable):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                input_data = {}
                if capture_input:
                    try:
                        input_data = {"args": str(args[:2])[:200]}
                    except Exception:
                        pass
                run_id = self.start_run(name=name, run_type=run_type,
                                        inputs=input_data, tags=tags or [])
                t0    = time.time()
                error = None
                result = None
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as exc:
                    error = str(exc)
                    raise
                finally:
                    out = {"duration_ms": int((time.time() - t0) * 1000)}
                    if capture_output and result is not None:
                        try:
                            out["result_type"] = type(result).__name__
                            if isinstance(result, str):
                                out["preview"] = result[:300]
                        except Exception:
                            pass
                    self.end_run(run_id, outputs=out, error=error)
            return wrapper
        return decorator


tracer = LangSmithTracer()
