"""
Polaris API: endpoints to browse the Iceberg catalog and preview table data.
Only active when POLARIS_ENABLED=true.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_polaris():
    if not settings.POLARIS_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Polaris integration is disabled. Set POLARIS_ENABLED=true.",
        )
    from app.polaris.catalog import get_polaris_client
    return get_polaris_client()


# ─── Models ───────────────────────────────────────────────────────────────────

class TableInfo(BaseModel):
    namespace: str
    table_name: str
    full_name: str
    schema_fields: List[str]
    row_count: Optional[int] = None


class NamespaceInfo(BaseModel):
    namespaces: List[str]
    table_count: int


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/polaris/status")
async def polaris_status():
    """Check Polaris connection status."""
    if not settings.POLARIS_ENABLED:
        return {"enabled": False, "message": "Set POLARIS_ENABLED=true to activate"}

    from app.polaris.catalog import get_polaris_client
    client = get_polaris_client()
    available = client.is_available()
    return {
        "enabled": True,
        "connected": available,
        "uri": settings.POLARIS_URI,
        "warehouse": settings.POLARIS_WAREHOUSE,
        "namespace": settings.POLARIS_NAMESPACE,
        "catalog_name": settings.POLARIS_CATALOG_NAME,
    }


@router.get("/polaris/namespaces")
async def list_namespaces():
    """List all namespaces in the Polaris catalog."""
    client = _require_polaris()
    try:
        namespaces = client.list_namespaces()
        tables = client.list_tables()
        return NamespaceInfo(namespaces=namespaces, table_count=len(tables))
    except Exception as e:
        logger.error(f"Polaris list_namespaces error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/polaris/tables")
async def list_tables(namespace: Optional[str] = Query(None)):
    """List Iceberg tables in a namespace (or all namespaces)."""
    client = _require_polaris()
    try:
        tables = client.list_tables(namespace=namespace)
        return {
            "total": len(tables),
            "namespace_filter": namespace,
            "tables": [
                TableInfo(
                    namespace=t.namespace,
                    table_name=t.table_name,
                    full_name=t.full_name,
                    schema_fields=t.schema_fields,
                    row_count=t.row_count,
                )
                for t in tables
            ],
        }
    except Exception as e:
        logger.error(f"Polaris list_tables error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/polaris/tables/{full_name:path}/preview")
async def preview_table(
    full_name: str,
    rows: int = Query(default=20, ge=1, le=1000),
    columns: Optional[str] = Query(default=None, description="Comma-separated column names"),
):
    """
    Preview rows from an Iceberg table.
    full_name format: namespace.table_name (e.g. MY_DB.MY_SCHEMA.MY_TABLE)
    """
    client = _require_polaris()
    try:
        col_list = [c.strip() for c in columns.split(",")] if columns else None
        df = client.read_table(full_name, row_limit=rows, columns=col_list)

        return {
            "table": full_name,
            "rows_returned": len(df),
            "columns": list(df.columns),
            "data": df.to_dict(orient="records"),
            "dtypes": {col: str(dt) for col, dt in df.dtypes.items()},
        }
    except Exception as e:
        logger.error(f"Polaris preview error for '{full_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/polaris/tables/{full_name:path}/stats")
async def table_stats(full_name: str):
    """
    Return descriptive statistics for an Iceberg table.
    """
    client = _require_polaris()
    try:
        df = client.read_table(full_name, row_limit=50000)
        desc = df.describe(include="all")

        stats = {}
        for col in desc.columns:
            stats[col] = {
                k: (None if str(v) == "nan" else v)
                for k, v in desc[col].to_dict().items()
            }

        return {
            "table": full_name,
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "dtypes": {col: str(dt) for col, dt in df.dtypes.items()},
            "statistics": stats,
        }
    except Exception as e:
        logger.error(f"Polaris stats error for '{full_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/polaris/index")
async def index_polaris_tables(request: Request, namespace: Optional[str] = None):
    """
    Index all Polaris tables into the RAG pipeline.
    Triggers a full re-index using Polaris as the file source.
    """
    if not settings.POLARIS_ENABLED:
        raise HTTPException(status_code=503, detail="Polaris not enabled")

    rag_pipeline = request.app.state.rag_pipeline
    try:
        stats = await rag_pipeline.index_all()
        return {
            "status": "indexed",
            "source": "polaris",
            **stats,
        }
    except Exception as e:
        logger.error(f"Polaris indexing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
