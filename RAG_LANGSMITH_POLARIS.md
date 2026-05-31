# RAG + LangSmith + Polaris — Implementation Guide

Complete reference for the three new capabilities added in v2.

---

## 1. Full RAG Pipeline

### Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Query Transformer  (query_transformer.py)           │
│  ├── Query Expansion  → 3 alternative queries        │
│  └── HyDE            → hypothetical document        │
└─────────────────────┬───────────────────────────────┘
                      │  N queries
                      ▼
┌─────────────────────────────────────────────────────┐
│  Vector Store  (vector_store.py)                     │
│  ├── FAISS Semantic Search  (cosine similarity)      │
│  ├── BM25 Keyword Search    (rank-bm25)              │
│  └── Hybrid Fusion          (RRF algorithm)          │
└─────────────────────┬───────────────────────────────┘
                      │  top-K candidates
                      ▼
┌─────────────────────────────────────────────────────┐
│  Reranker  (reranker.py)                             │
│  ├── CrossEncoder (local, ms-marco-MiniLM)           │
│  └── Cohere Rerank (API, best quality)               │
└─────────────────────┬───────────────────────────────┘
                      │  top-4 final chunks
                      ▼
┌─────────────────────────────────────────────────────┐
│  LLM Synthesis  (orchestrator.py)                    │
│  └── Streams answer token-by-token via SSE           │
└─────────────────────────────────────────────────────┘
```

### Chunking strategies

| Strategy | Config | Best for |
|----------|--------|----------|
| `recursive` | `CHUNK_STRATEGY=recursive` | Documents, reports (default) |
| `fixed` | `CHUNK_STRATEGY=fixed` | Structured data, logs |
| `semantic` | `CHUNK_STRATEGY=semantic` | Long narratives, articles |

### Retrieval modes

| Mode | Config | Description |
|------|--------|-------------|
| `hybrid` | `RETRIEVAL_MODE=hybrid` | BM25 + FAISS via RRF (recommended) |
| `semantic` | `RETRIEVAL_MODE=semantic` | FAISS only |
| `bm25` | `RETRIEVAL_MODE=bm25` | Keyword only (no embedding needed) |

### Embedding providers

| Provider | Config | Cost | Quality |
|----------|--------|------|---------|
| Local (MiniLM) | `EMBEDDING_PROVIDER=local` | Free | Good |
| OpenAI | `EMBEDDING_PROVIDER=openai` | ~$0.02/M tokens | Better |

### Enabling reranking

```env
RERANKER_ENABLED=true
RERANKER_PROVIDER=cross-encoder   # local, free
# or
RERANKER_PROVIDER=cohere          # API, best quality
COHERE_API_KEY=your_key_here
```

### Query expansion + HyDE

```env
QUERY_EXPANSION_ENABLED=true   # generate 3 sub-queries per question
HYDE_ENABLED=true              # generate hypothetical doc for retrieval
```

---

## 2. LangSmith Observability

### Setup

1. Sign up at https://smith.langchain.com (free tier available)
2. Create an API key at Settings → API Keys
3. Add to `.env`:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__your_key_here
LANGCHAIN_PROJECT=copilot-analyst
```

### What gets traced

Every chat invocation creates a **run tree** in LangSmith:

```
copilot_analyst_chat  (root)
  ├── plan_step
  ├── rag_retrieval
  │     └── chunks_retrieved, files_used, retrieval_ms
  └── llm_generation
        └── prompt_preview, output_preview, tokens_estimate
```

You see in LangSmith:
- Full prompt sent to LLM
- Token counts and estimated cost
- Latency per step
- Which files were retrieved
- Errors with full tracebacks

### Feedback loop

After a chat response, the frontend sends the `langsmith_run_id` (returned in the `done` chunk).
Users clicking thumbs-up/thumbs-down hits `POST /api/observability/feedback`:

```http
POST /api/observability/feedback
{
  "run_id": "uuid-from-done-chunk",
  "positive": true,
  "comment": "Answer was accurate"
}
```

### Building evaluation datasets

```http
POST /api/observability/eval-example
{
  "query": "What is total Q1 revenue?",
  "answer": "Total Q1 revenue was $43,800 across all regions.",
  "files_used": ["sales.csv"]
}
```

This adds the pair to the `copilot-analyst-eval` dataset in LangSmith for automated evaluation.

### Check status

```
GET /api/observability/status
```

---

## 3. Snowflake Polaris Catalog

### What Polaris provides

Polaris is Snowflake's open-source **Apache Iceberg REST catalog**. It lets you:
- Treat Iceberg tables as first-class file sources (just like CSV/Parquet)
- Get schema information, statistics, and filtered scans
- Index and query petabyte-scale data through the same RAG pipeline

### Prerequisites

```bash
pip install 'pyiceberg[pyarrow]'
```

### Setup

1. In Snowflake, enable Polaris Open Catalog
2. Create a service credential (client_id + client_secret)
3. Add to `.env`:

```env
FILE_SOURCE=polaris
POLARIS_ENABLED=true
POLARIS_URI=https://<account>.snowflakecomputing.com/polaris/api/catalog
POLARIS_CREDENTIAL=<client_id>:<client_secret>
POLARIS_WAREHOUSE=<your_warehouse>
POLARIS_NAMESPACE=MY_DB.MY_SCHEMA   # optional namespace filter
```

### API endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/polaris/status` | Connection status |
| `GET /api/polaris/namespaces` | List all namespaces |
| `GET /api/polaris/tables` | List Iceberg tables |
| `GET /api/polaris/tables/{name}/preview?rows=20` | Preview table data |
| `GET /api/polaris/tables/{name}/stats` | Descriptive statistics |
| `POST /api/polaris/index` | Re-index all Polaris tables into RAG |

### Example queries after indexing Polaris tables

```
Summarize all tables and show their row counts and schemas

Compare revenue trends across MY_DB.SALES_FACT and MY_DB.REGIONAL_SUMMARY

Which customer segments in MY_DB.CUSTOMERS have the highest churn risk?
```

### Reading a table in Python

```python
from app.polaris.catalog import get_polaris_client

client = get_polaris_client()

# List tables
tables = client.list_tables(namespace="MY_DB.MY_SCHEMA")
for t in tables:
    print(t.full_name, t.schema_fields)

# Read as DataFrame
df = client.read_table("MY_DB.MY_SCHEMA.SALES_FACT", row_limit=10000)
print(df.describe())

# Read with filter (PyIceberg expression)
from pyiceberg.expressions import GreaterThan
df_filtered = client.read_table(
    "MY_DB.MY_SCHEMA.SALES_FACT",
    filter_expr=GreaterThan("revenue", 10000),
    columns=["date", "product", "revenue"],
)
```

---

## New API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/observability/status` | GET | RAG + LangSmith config |
| `/api/observability/feedback` | POST | Submit thumbs up/down |
| `/api/observability/eval-example` | POST | Add to eval dataset |
| `/api/polaris/status` | GET | Polaris connection |
| `/api/polaris/namespaces` | GET | List namespaces |
| `/api/polaris/tables` | GET | List Iceberg tables |
| `/api/polaris/tables/{name}/preview` | GET | Preview rows |
| `/api/polaris/tables/{name}/stats` | GET | Descriptive stats |
| `/api/polaris/index` | POST | Index Polaris tables |
| `/api/files/indexed` | GET | Now includes RAG metadata |

---

## New Files Reference

```
backend/app/
├── rag/
│   ├── embeddings.py        Local SentenceTransformer + OpenAI embeddings
│   ├── chunker.py           Fixed / Recursive / Semantic chunking
│   ├── vector_store.py      FAISS + BM25 hybrid search with persistence
│   ├── reranker.py          CrossEncoder + Cohere reranking
│   ├── query_transformer.py Query expansion + HyDE
│   └── pipeline.py          End-to-end RAG orchestration
│
├── observability/
│   ├── langsmith_tracer.py  LangSmith client wrapper + decorators
│   └── metrics.py           Per-invocation metrics + feedback API helpers
│
├── polaris/
│   └── catalog.py           PyIceberg Polaris client + FileSource adapter
│
└── api/
    ├── observability.py     /api/observability/* endpoints
    └── polaris.py           /api/polaris/* endpoints
```
