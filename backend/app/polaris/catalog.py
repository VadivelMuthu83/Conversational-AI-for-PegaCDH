"""
Snowflake Polaris (Open Catalog) integration.

Polaris is an open-source Apache Iceberg REST catalog.
Snowflake hosts it at: https://<account>.snowflakecomputing.com/polaris/api/catalog

This module:
  1. Connects to the Polaris catalog using PyIceberg
  2. Lists available namespaces and tables
  3. Reads Iceberg tables as pandas DataFrames (via PyArrow)
  4. Exposes the same FileInfo/ParsedFile interface as local/S3 sources
     so the rest of the pipeline is source-agnostic

Prerequisites:
  pip install pyiceberg[pyarrow] pandas pyarrow

Environment variables:
  POLARIS_ENABLED=true
  POLARIS_URI=https://<account>.snowflakecomputing.com/polaris/api/catalog
  POLARIS_CREDENTIAL=<client_id>:<client_secret>
  POLARIS_WAREHOUSE=<warehouse_name>
  POLARIS_NAMESPACE=<NAMESPACE>              # e.g. "MY_DB" or "MY_DB.MY_SCHEMA"
  POLARIS_CATALOG_NAME=polaris              # logical name, keep as "polaris"
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.file_source import FileInfo

logger = logging.getLogger(__name__)


class PolarisTable:
    """Represents one Iceberg table read from the Polaris catalog."""

    def __init__(self, namespace: str, table_name: str, full_name: str,
                 schema_fields: List[str], row_count: Optional[int] = None):
        self.namespace = namespace
        self.table_name = table_name
        self.full_name = full_name           # "namespace.table_name"
        self.schema_fields = schema_fields
        self.row_count = row_count

    def as_file_info(self) -> FileInfo:
        return FileInfo(
            name=f"{self.full_name}.iceberg",
            path=self.full_name,
            size=0,                           # unknown until scan
            last_modified=None,
        )


class PolarisClient:
    """
    Wraps PyIceberg to interact with the Snowflake Polaris catalog.
    """

    def __init__(self):
        self._catalog = None
        self._connected = False

    def _get_catalog(self):
        if self._catalog is not None:
            return self._catalog

        if not settings.POLARIS_URI:
            raise ValueError("POLARIS_URI is not set in environment")
        if not settings.POLARIS_CREDENTIAL:
            raise ValueError("POLARIS_CREDENTIAL is not set (format: client_id:client_secret)")

        try:
            from pyiceberg.catalog import load_catalog
        except ImportError:
            raise ImportError(
                "pyiceberg is not installed. Run: pip install 'pyiceberg[pyarrow]'"
            )

        # Parse credential
        cred_parts = settings.POLARIS_CREDENTIAL.split(":", 1)
        if len(cred_parts) != 2:
            raise ValueError("POLARIS_CREDENTIAL must be in format client_id:client_secret")
        client_id, client_secret = cred_parts

        catalog_config = {
            "type": "rest",
            "uri": settings.POLARIS_URI,
            "credential": f"{client_id}:{client_secret}",
        }
        if settings.POLARIS_WAREHOUSE:
            catalog_config["warehouse"] = settings.POLARIS_WAREHOUSE

        logger.info(f"Connecting to Polaris catalog at {settings.POLARIS_URI}")
        self._catalog = load_catalog(settings.POLARIS_CATALOG_NAME, **catalog_config)
        self._connected = True
        logger.info("Polaris catalog connected successfully")
        return self._catalog

    # ─── Namespace / Table discovery ──────────────────────────────────────────

    def list_namespaces(self) -> List[str]:
        catalog = self._get_catalog()
        namespaces = catalog.list_namespaces()
        return [".".join(ns) for ns in namespaces]

    def list_tables(self, namespace: Optional[str] = None) -> List[PolarisTable]:
        catalog = self._get_catalog()
        ns = namespace or settings.POLARIS_NAMESPACE

        results = []
        namespaces_to_scan = [ns] if ns else self.list_namespaces()

        for ns_str in namespaces_to_scan:
            try:
                ns_tuple = tuple(ns_str.split("."))
                tables = catalog.list_tables(ns_tuple)
                for tbl_id in tables:
                    tbl_name = ".".join(tbl_id)
                    try:
                        schema_fields = self._get_schema_fields(tbl_id)
                        results.append(PolarisTable(
                            namespace=ns_str,
                            table_name=tbl_id[-1],
                            full_name=tbl_name,
                            schema_fields=schema_fields,
                        ))
                    except Exception as e:
                        logger.warning(f"Could not introspect table {tbl_name}: {e}")
                        results.append(PolarisTable(
                            namespace=ns_str,
                            table_name=tbl_id[-1],
                            full_name=tbl_name,
                            schema_fields=[],
                        ))
            except Exception as e:
                logger.error(f"Error listing tables in namespace '{ns_str}': {e}")

        logger.info(f"Polaris: found {len(results)} tables")
        return results

    def _get_schema_fields(self, table_id: Tuple) -> List[str]:
        catalog = self._get_catalog()
        tbl = catalog.load_table(table_id)
        return [f.name for f in tbl.schema().fields]

    # ─── Data reading ─────────────────────────────────────────────────────────

    def read_table(
        self,
        full_name: str,
        row_limit: int = 10000,
        columns: Optional[List[str]] = None,
        filter_expr=None,
    ):
        """
        Read an Iceberg table into a pandas DataFrame.

        Args:
            full_name  : "namespace.table_name"
            row_limit  : max rows to read (default 10k for safety)
            columns    : column subset (None = all)
            filter_expr: PyIceberg expression e.g. GreaterThan("col", 0)

        Returns:
            pandas.DataFrame
        """
        catalog = self._get_catalog()
        table_id = tuple(full_name.split("."))
        tbl = catalog.load_table(table_id)

        scan = tbl.scan(limit=row_limit)
        if columns:
            scan = scan.select(*columns)
        if filter_expr is not None:
            scan = scan.filter(filter_expr)

        arrow_table = scan.to_arrow()
        df = arrow_table.to_pandas()
        logger.info(
            f"Polaris read '{full_name}': {len(df)} rows × {len(df.columns)} cols"
        )
        return df

    def read_table_as_text(
        self, full_name: str, row_limit: int = 5000
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Read table and return (text_repr, metadata_dict) for RAG indexing.
        """
        df = self.read_table(full_name, row_limit=row_limit)
        row_count = len(df)
        columns = list(df.columns)

        summary_parts = [
            f"Iceberg Table: {full_name}",
            f"Rows: {row_count}",
            f"Columns: {', '.join(columns)}",
        ]

        try:
            desc = df.describe(include="all").to_string()
            summary_parts.append(f"\nStatistics:\n{desc}")
        except Exception:
            pass

        sample = df.head(50).to_string(index=False)
        full_text = "\n".join(summary_parts) + f"\n\nSample rows:\n{sample}"

        metadata = {
            "source": "polaris",
            "table": full_name,
            "row_count": row_count,
            "columns": columns,
        }
        return full_text, metadata

    # ─── FileInfo adapter (for pipeline compatibility) ─────────────────────────

    def list_as_file_infos(self) -> List[FileInfo]:
        """Return Polaris tables as FileInfo objects (same interface as local/S3)."""
        tables = self.list_tables()
        return [t.as_file_info() for t in tables]

    def read_file(self, path: str) -> bytes:
        """
        Compatibility shim: read a Polaris table and return CSV bytes.
        path format: "namespace.table_name"
        """
        df = self.read_table(path)
        return df.to_csv(index=False).encode("utf-8")

    def is_available(self) -> bool:
        try:
            self._get_catalog()
            return True
        except Exception as e:
            logger.warning(f"Polaris not available: {e}")
            return False


# ─── Polaris file source (integrates with existing file_source.py) ────────────

class PolarisFileSource:
    """
    Drop-in replacement for LocalFileSource / S3FileSource when FILE_SOURCE=polaris.
    """

    def __init__(self):
        self._client = PolarisClient()

    def list_files(self) -> List[FileInfo]:
        return self._client.list_as_file_infos()

    def read_file(self, path: str) -> bytes:
        return self._client.read_file(path)

    def file_exists(self, path: str) -> bool:
        tables = self._client.list_tables()
        return any(t.full_name == path for t in tables)


# ─── Singleton ────────────────────────────────────────────────────────────────

_client: Optional[PolarisClient] = None


def get_polaris_client() -> PolarisClient:
    global _client
    if _client is None:
        _client = PolarisClient()
    return _client
