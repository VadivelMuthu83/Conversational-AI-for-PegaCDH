# Copilot Analyst — Complete Setup & Test Guide

## Table of Contents
1. Prerequisites
2. First-time setup
3. Configure environment
4. Run locally (without Docker)
5. Run with Docker
6. Verify the application is working
7. Run the test suite
8. Test all features (step-by-step)
9. Test CDH knowledge articles
10. Test document generation
11. Troubleshooting

---

## 1. Prerequisites

| Tool | Minimum version | Check |
|------|----------------|-------|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Git | any | `git --version` |
| Docker (optional) | 24+ | `docker --version` |
| Docker Compose (optional) | 2+ | `docker compose version` |

You also need **at least one** LLM API key:
- Anthropic: https://console.anthropic.com → API Keys
- OpenAI: https://platform.openai.com → API Keys
- Google Gemini: https://aistudio.google.com → Get API Key

---

## 2. First-time Setup

```bash
# 1. Unzip the project
unzip copilot-analyst-cdh-rag.zip
cd copilot-analyst

# 2. Confirm structure
ls
# Should show: backend/  frontend/  sample-data/  docker-compose.yml  .env.example
```

---

## 3. Configure Environment

```bash
# Copy the template
cp .env.example .env

# Open .env in your editor and set your API key
# Minimum required changes — everything else has working defaults:
```

**Minimum `.env` for local testing with sample data:**

```env
# LLM — pick one and add its key
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-real-key-here

# Files — use the bundled sample data
KNOWLEDGE_PATH=./sample-data

# RAG index location
RAG_STORE_PATH=./index

# Embedding model (downloads ~80MB on first run, no API key needed)
EMBEDDING_MODEL=all-MiniLM-L6-v2

# LangSmith — optional, leave blank to disable
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=

# Everything else — keep defaults
FILE_SOURCE=local
EMBEDDING_PROVIDER=local
RETRIEVAL_MODE=hybrid
RAG_ENABLED=true
STREAMING_ENABLED=true
```

---

## 4. Run Locally (Without Docker)

### 4a. Backend

```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate        # Mac/Linux
# OR
venv\Scripts\activate           # Windows

# Install dependencies
# Note: torch is large (~800MB). First install may take 5-10 minutes.
pip install -r requirements.txt

# Copy .env into backend folder
cp ../.env .env

# Start the backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected startup output:**
```
INFO | Starting Copilot Analyst v2.0.0
INFO | Files path  : ./sample-data   (KNOWLEDGE_PATH or LOCAL_FILES_PATH)
INFO | Index dir   : ./index         (RAG_STORE_PATH or INDEX_DIR)
INFO | Embed model : all-MiniLM-L6-v2
INFO | LLM         : anthropic
INFO | RAG mode    : hybrid | Reranker: False
INFO | LangSmith   : disabled
INFO | KnowledgeArticleParser ready
INFO | Indexing 9 files from ./sample-data ...
INFO | KB article indexed: NBA_Strategy_Guide.md → 12 chunks
INFO | KB article indexed: KB-CDH-001-ADM-Setup.md → 9 chunks
INFO | KB article indexed: CDH_DataDictionary.md → 6 chunks
INFO | IH aggregated: 96 rows (from 96 raw)
INFO | Index built: 9 files → 187 chunks
INFO | Application startup complete.
```

### 4b. Frontend (new terminal)

```bash
cd frontend

# Install packages
npm install

# Copy env
cp .env.example .env.local

# Start dev server
npm run dev
```

**Expected output:**
```
  VITE v5.x.x  ready in 800ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: http://0.0.0.0:3000/
```

Open **http://localhost:3000** — you should see the Copilot Analyst chat interface.

---

## 5. Run With Docker

```bash
# From project root (where docker-compose.yml lives)
cd copilot-analyst

# Make sure .env exists with your API key
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY (or OPENAI_API_KEY)

# Build and start both services
docker compose up --build

# First run downloads the embedding model — takes 3-5 minutes
# Watch for: "Application startup complete"
```

| Service | URL |
|---------|-----|
| Frontend UI | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

To stop: `Ctrl+C` then `docker compose down`

To rebuild after code changes: `docker compose up --build --force-recreate`

---

## 6. Verify the Application is Working

Run these checks in order. All should return HTTP 200.

### Check 1 — Backend health

```bash
curl http://localhost:8000/api/health
```

**Expected response:**
```json
{
  "status": "ok",
  "llm_provider": "anthropic",
  "file_source": "local",
  "indexed_files": 9,
  "indexed_chunks": 187,
  "streaming_enabled": true
}
```

✅ `indexed_files` > 0 means files were found and parsed  
✅ `indexed_chunks` > 0 means RAG index was built  
✅ `status: "ok"` means backend is ready

### Check 2 — Root info (confirms resolved env vars)

```bash
curl http://localhost:8000/ | python3 -m json.tool
```

**Expected response:**
```json
{
  "app": "Copilot Analyst",
  "version": "2.0.0",
  "rag_mode": "hybrid",
  "llm_provider": "anthropic",
  "files_path": "./sample-data",
  "index_dir": "./index",
  "embedding_model": "all-MiniLM-L6-v2",
  "langsmith": false,
  "langsmith_project": "pega-cdh-analyst",
  "polaris": false,
  "cdh_mode": true
}
```

✅ `files_path` should match your KNOWLEDGE_PATH  
✅ `embedding_model` should match your EMBEDDING_MODEL  
✅ `rag_mode: "hybrid"` confirms hybrid BM25+FAISS is active  

### Check 3 — Indexed files

```bash
curl http://localhost:8000/api/files/indexed | python3 -m json.tool
```

**Expected:**
```json
{
  "total_files": 9,
  "total_chunks": 187,
  "retrieval_mode": "hybrid",
  "embedding_provider": "local",
  "chunk_strategy": "recursive",
  "files": [...]
}
```

### Check 4 — CDH sources detected

```bash
curl http://localhost:8000/api/cdh/sources | python3 -m json.tool
```

**Expected:**
```json
{
  "cdh_data_sources": [
    {"source_id": "interaction_history", "display_name": "Interaction History (IH)", ...}
  ],
  "knowledge_articles": [
    {"file": "NBA_Strategy_Guide.md", "article_type": "nba_strategy_doc", "chunks": 12},
    {"file": "KB-CDH-001-ADM-Setup.md", "article_type": "pega_kb_article", "chunks": 9},
    {"file": "CDH_DataDictionary.md", "article_type": "data_dictionary", "chunks": 6}
  ],
  "total_indexed": 9
}
```

✅ Knowledge articles appear in `knowledge_articles`  
✅ Data files appear in `cdh_data_sources`  

### Check 5 — Knowledge articles list

```bash
curl http://localhost:8000/api/cdh/knowledge-articles | python3 -m json.tool
```

**Expected:**
```json
{
  "total_articles": 3,
  "articles": [
    {
      "filename": "CDH_DataDictionary.md",
      "article_type": "data_dictionary",
      "article_name": "Data Dictionary / Schema Doc",
      "sections": ["ADM Snapshot Fields", "CDH Data Dictionary", "Common Channel Values"],
      "chunk_count": 6
    }
  ]
}
```

### Check 6 — Observability status

```bash
curl http://localhost:8000/api/observability/status | python3 -m json.tool
```

**Expected:**
```json
{
  "langsmith_enabled": false,
  "rag_enabled": true,
  "retrieval_mode": "hybrid",
  "embedding_model": "all-MiniLM-L6-v2",
  "index_dir": "./index",
  "files_path": "./sample-data"
}
```

---

## 7. Run the Test Suite

```bash
cd backend
source venv/bin/activate

# Run all tests with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=app --cov-report=term-missing

# Run only a specific test class
pytest tests/test_full.py::TestChunkers -v
pytest tests/test_full.py::TestFileParser -v
pytest tests/test_full.py::TestLangSmithTracer -v

# Run only API tests
pytest tests/test_full.py -v -k "test_health or test_chat or test_files"
```

**Expected output:**
```
tests/test_full.py::TestChunkers::test_fixed_chunker_basic        PASSED
tests/test_full.py::TestChunkers::test_recursive_chunker_...      PASSED
tests/test_full.py::TestChunkers::test_chunk_metadata             PASSED
tests/test_full.py::TestChunkers::test_chunk_id_uniqueness        PASSED
tests/test_full.py::TestChunkers::test_get_chunker_factory        PASSED
tests/test_full.py::TestEmbeddings::test_local_embedding_...      PASSED
tests/test_full.py::TestVectorStore::test_bm25_search             PASSED
tests/test_full.py::TestVectorStore::test_hybrid_search_...       PASSED
tests/test_full.py::TestRerankers::test_passthrough_reranker      PASSED
tests/test_full.py::TestQueryTransformer::test_expand_...         PASSED
tests/test_full.py::TestFileParser::test_csv_parsing              PASSED
tests/test_full.py::TestFileParser::test_zip_parsing              PASSED
tests/test_full.py::TestLangSmithTracer::test_tracer_disabled     PASSED
tests/test_full.py::TestPolarisClient::test_polaris_raises_...    PASSED
tests/test_full.py::test_health_endpoint                          PASSED
tests/test_full.py::test_chat_sync                                PASSED
tests/test_full.py::test_files_indexed                            PASSED
...

============= 35 passed in 12.4s =============
```

---

## 8. Test All Features (Step-by-Step)

### Test A — Basic chat via API

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What files are available and what do they contain?",
    "stream": false
  }' | python3 -m json.tool
```

**Expected:** JSON with `content` field containing a summary of all indexed files.

### Test B — CDH-aware chat

```bash
curl -X POST http://localhost:8000/api/cdh/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Which NBA actions have the highest accept rate?",
    "stream": false
  }' | python3 -m json.tool
```

**Expected:** Response includes `cdh_sources` field listing which CDH data sources were used.

### Test C — Knowledge article query

```bash
curl -X POST http://localhost:8000/api/cdh/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How should I configure ADM models and what AUC threshold should I use?",
    "stream": false,
    "kb_only": true
  }' | python3 -m json.tool
```

**Expected:** Answer drawn from KB-CDH-001-ADM-Setup.md — mentions AUC thresholds table (> 0.80 Excellent, < 0.60 Poor).

### Test D — Streaming chat (Server-Sent Events)

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "message": "Summarise all sales data by region",
    "stream": true
  }'
```

**Expected:** Lines of `data: {...}` SSE events, including:
- `data: {"type": "status", "content": "Analysing your question..."}`
- `data: {"type": "text", "content": "## Summary\n\n"}`
- `data: {"type": "done", ...}`
- `data: [DONE]`

### Test E — File refresh

```bash
curl -X POST http://localhost:8000/api/files/refresh | python3 -m json.tool
```

**Expected:**
```json
{"status": "refreshed", "files_parsed": 9, "total_chunks": 187, "index_time_ms": 3200}
```

### Test F — LangSmith observability status

```bash
curl http://localhost:8000/api/observability/status | python3 -m json.tool
```

### Test G — List document templates

```bash
curl http://localhost:8000/api/cdh/templates | python3 -m json.tool
```

**Expected:** 6 templates including `nba_performance_report`, `adm_health_report`, etc.

### Test H — List Polaris status (disabled)

```bash
curl http://localhost:8000/api/polaris/status | python3 -m json.tool
```

**Expected:** `{"enabled": false, "message": "Set POLARIS_ENABLED=true to activate"}`

### Test I — Swagger UI

Open in browser: **http://localhost:8000/docs**

You can test every endpoint interactively. Click any endpoint → "Try it out" → fill parameters → Execute.

---

## 9. Test CDH Knowledge Articles

### Add your own PDFs and test

```bash
# Copy a Pega PDF guide into the sample-data/knowledge folder
cp ~/Downloads/CDH_Configuration_Guide.pdf ./sample-data/knowledge/

# Trigger re-index
curl -X POST http://localhost:8000/api/files/refresh

# Verify it was detected as a knowledge article
curl http://localhost:8000/api/cdh/knowledge-articles | python3 -m json.tool

# Query it
curl -X POST http://localhost:8000/api/cdh/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What does the configuration guide say about setting up data flows?",
    "stream": false,
    "kb_only": true
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['content'])"
```

### Test with bundled knowledge articles

```bash
# Query the NBA Strategy Guide
curl -X POST http://localhost:8000/api/cdh/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain the arbitration priority formula and engagement policy rules",
    "stream": false
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['content'][:1000])"

# Query the data dictionary
curl -X POST http://localhost:8000/api/cdh/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What does the Propensity field mean and what range does it have?",
    "stream": false,
    "kb_only": true
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['content'])"
```

---

## 10. Test Document Generation

### Generate NBA Performance Report

```bash
curl -X POST http://localhost:8000/api/cdh/generate-document \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "question": "Analyse our sales performance across all products and regions",
    "doc_type": "nba_performance_report"
  }'
```

**Expected:** SSE stream of `text` chunks building a full Markdown document with sections:
- Executive Summary
- Action Performance by Channel
- Weekly Trend Analysis
- Underperforming Actions
- Recommended Actions

### Generate Knowledge Synthesis Report

```bash
curl -X POST http://localhost:8000/api/cdh/generate-document \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "question": "Summarise all CDH configuration and ADM setup best practices",
    "doc_type": "kb_synthesis_report"
  }'
```

**Expected:** Answer built from KB articles only — cites NBA_Strategy_Guide.md, KB-CDH-001-ADM-Setup.md, CDH_DataDictionary.md.

### Test in the UI

1. Open http://localhost:3000
2. Click **Files** button (top right) to see what is indexed
3. Try these queries in the chat:

```
What files are indexed and what CDH data sources are available?

Summarise all sales data by product and region

Which products have the highest profit margin?

How does arbitration priority work according to the strategy guide?

What AUC threshold should ADM models meet?

Generate a full NBA performance analysis report
```

---

## 11. Troubleshooting

### Backend won't start

**Error: `ModuleNotFoundError: No module named 'app'`**
```bash
# Make sure you are inside the backend directory
cd backend
uvicorn app.main:app --reload --port 8000
# NOT: uvicorn backend.app.main:app
```

**Error: `pydantic_settings.env_file_encoding`**
```bash
pip install pydantic-settings --upgrade
```

**Error: `No files indexed (indexed_files: 0)`**
```bash
# Check KNOWLEDGE_PATH exists and has files
ls ./sample-data/
# Check the path in .env matches
grep KNOWLEDGE_PATH .env
# Try the absolute path
echo $(pwd)/sample-data
# Set in .env: KNOWLEDGE_PATH=/absolute/path/to/sample-data
```

**Error: `torch` install fails on Windows**
```bash
# Install CPU-only torch first
pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu
# Then install the rest
pip install -r requirements.txt
```

### Frontend won't start

**Error: `npm install` fails**
```bash
# Clear cache and retry
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

**Error: `Failed to fetch /api/health` in browser**
```bash
# Confirm backend is running
curl http://localhost:8000/api/health

# Check vite.config.ts proxy — should point to port 8000
cat frontend/vite.config.ts | grep target
```

### Docker issues

**Error: `port 8000 already in use`**
```bash
# Find and stop the conflicting process
lsof -ti:8000 | xargs kill -9
docker compose up --build
```

**Error: `No files found` in Docker but files exist locally**
```bash
# Check the volume mount in docker-compose.yml
# ./sample-data is mounted as /data (read-only)
# Set in .env: KNOWLEDGE_PATH=/data
grep KNOWLEDGE_PATH .env
```

**Slow first Docker build (downloading torch)**
```bash
# Normal — torch is ~800MB
# Subsequent builds use Docker layer cache and are fast
# Expected first build time: 8-15 minutes depending on internet speed
```

### LLM returns "Mock" responses

```bash
# No API key configured — check .env
grep "API_KEY\|LLM_PROVIDER" .env

# Confirm the key is actually set (not blank)
python3 -c "
from dotenv import load_dotenv; import os
load_dotenv('.env')
print('Provider:', os.getenv('LLM_PROVIDER'))
print('Key set:', bool(os.getenv('ANTHROPIC_API_KEY') or os.getenv('OPENAI_API_KEY')))
"
```

### Embedding model download is slow

The `all-MiniLM-L6-v2` model (~80MB) downloads from HuggingFace on first run.
```bash
# Pre-download manually
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
# Model cached at: ~/.cache/huggingface/hub/
```

### RAG returns wrong answers

```bash
# Check what is actually in the index
curl http://localhost:8000/api/files/indexed | python3 -m json.tool

# Check retrieval mode
curl http://localhost:8000/api/observability/status | python3 -m json.tool

# Force a full re-index
curl -X POST http://localhost:8000/api/files/refresh

# Try a more specific query — vague queries retrieve mixed results
```

---

## Quick Reference

| What | Command |
|------|---------|
| Start backend | `cd backend && uvicorn app.main:app --reload --port 8000` |
| Start frontend | `cd frontend && npm run dev` |
| Start with Docker | `docker compose up --build` |
| Run tests | `cd backend && pytest tests/ -v` |
| Check health | `curl localhost:8000/api/health` |
| List indexed files | `curl localhost:8000/api/files/indexed` |
| List KB articles | `curl localhost:8000/api/cdh/knowledge-articles` |
| Refresh index | `curl -X POST localhost:8000/api/files/refresh` |
| API docs | http://localhost:8000/docs |
| Frontend UI | http://localhost:3000 |
