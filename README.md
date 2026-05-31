# 🔬 Copilot Analyst

A production-ready, Copilot-style chat application for AI-powered analysis of local or S3 files.

**Stack:** FastAPI + React + Streaming SSE + FAISS + Multi-LLM (Anthropic Claude / OpenAI / Gemini)

---

## ✨ Features

| Feature | Detail |
|---------|--------|
| Copilot-style UI | New chat, chat history, streaming, disabled send, mobile-responsive |
| Multi-format parsing | CSV, JSON, JSONL, Excel, Parquet, ZIP, TXT, MD, YAML |
| Agentic orchestration | Plan → Retrieve → Synthesize pipeline |
| Multi-LLM | Anthropic Claude, OpenAI GPT-4o, Google Gemini — switchable at runtime |
| Vector search | FAISS semantic search (degrades gracefully to keyword search) |
| Streaming responses | Server-Sent Events (SSE) with intermediate status updates |
| Local + S3 | Configurable file source via env vars |
| Structured outputs | Tables, JSON summaries, confidence scores in UI |
| Large files | Chunking, batching, configurable limits |

---

## 🚀 Quick Start (Local)

### Prerequisites

- Python 3.10+ 
- Node.js 18+
- At least one LLM API key (Anthropic, OpenAI, or Gemini)

### 1. Set up environment

```bash
cp .env.example .env
# Edit .env — add your API key and choose LLM_PROVIDER
```

### 2. Run (one command)

```bash
bash scripts/run-local.sh
```

Or manually:

```bash
# Terminal 1 — Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env .env
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**

---

## 🐳 Docker

```bash
cp .env.example .env   # edit your API keys
docker compose up --build
```

- Frontend: http://localhost:3000  
- Backend API: http://localhost:8000  
- API docs: http://localhost:8000/docs

---

## ⚙️ Configuration

All settings via `.env` (see `.env.example` for full list):

### LLM Provider

```env
LLM_PROVIDER=anthropic      # or openai | gemini
ANTHROPIC_API_KEY=sk-...
# OPENAI_API_KEY=sk-...
# GEMINI_API_KEY=AIza...
```

### File Source

```env
# Local files (default)
FILE_SOURCE=local
LOCAL_FILES_PATH=./sample-data

# AWS S3
FILE_SOURCE=s3
S3_BUCKET=my-data-bucket
S3_PREFIX=datasets/          # optional subfolder
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

### Performance Tuning

```env
CHUNK_SIZE=1000          # chars per chunk (increase for longer docs)
CHUNK_OVERLAP=150        # overlap between chunks
TOP_K_RETRIEVAL=8        # chunks retrieved per query
MAX_FILE_SIZE_MB=500     # skip files larger than this
MAX_WORKERS=4            # parallel workers
STREAMING_ENABLED=true
```

---

## 📁 Sample Data

The `sample-data/` folder includes:

| File | Description |
|------|-------------|
| `sales.csv` | 96 rows of product/region/monthly sales |
| `customers.json` | 20 customer records with tier, spend, churn risk |
| `products.json` | 8 product SKUs with pricing and stock |
| `metrics.csv` | Monthly SaaS metrics (users, revenue, churn) |
| `notes.txt` | Analyst notes for context |
| `archive.zip` | ZIP with `regional_summary.csv` + `targets.json` inside |

---

## 🧪 Sample Queries

Try these after starting the app:

```
Summarize all files and list key metrics from each

Which product has the highest profit margin?

Compare revenue across regions — which performed best?

What is the monthly revenue trend from metrics.csv?

List customers with the highest churn risk

How many files are indexed and what are their schemas?

Show me a table of sales by region and quarter
```

---

## ✅ Acceptance Tests

### Test 1: Local mixed-file analysis

1. Start the app (local or Docker)
2. Open http://localhost:3000
3. Send: **"Summarize all files and list key metrics. Which files were used?"**
4. ✅ Expected: Structured table summarizing each file, file tags shown in response footer

### Test 2: S3 file source

1. Set in `.env`:
   ```env
   FILE_SOURCE=s3
   S3_BUCKET=your-bucket
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   ```
2. Restart backend: `docker compose restart backend`
3. Send: **"What files are available and what do they contain?"**
4. ✅ Expected: Files listed from S3 bucket

### Test 3: Streaming + large file

1. Keep app running with sample data
2. Send: **"Analyze all sales data by month — show revenue, profit, and growth trends"**
3. ✅ Expected: Status updates appear while streaming, final structured table rendered

### Test 4: Provider switching

1. In the UI sidebar, switch LLM Provider to OpenAI (requires `OPENAI_API_KEY`)
2. Send: **"Compare Widget A vs Widget C on all metrics"**
3. ✅ Expected: Response from different provider

---

## 📡 API Reference

### `POST /api/chat`
```json
{
  "session_id": "uuid",
  "message": "What are total sales by region?",
  "stream": true,
  "llm_provider": "anthropic",
  "history": []
}
```
Returns SSE stream (when `stream: true`) or JSON.

### `GET /api/files/indexed`
Lists all indexed files with metadata.

### `POST /api/files/refresh`
Re-scans and re-indexes all files.

### `GET /api/health`
Returns backend status, provider info, file/chunk counts.

---

## 🏗 Architecture

```
Frontend (React + Vite)
  └── SSE streaming ──→ Backend (FastAPI)
                            ├── AgentOrchestrator
                            │     ├── Plan (LLM call)
                            │     ├── Retrieve (FAISS / keyword)
                            │     └── Synthesize (streaming LLM)
                            ├── IndexService (FAISS + chunks)
                            ├── FileParser (csv/json/xlsx/parquet/zip)
                            └── FileSource (local / S3)
```

---

## 📈 Performance Notes

### Large datasets
- Files are chunked at `CHUNK_SIZE` chars with `CHUNK_OVERLAP` overlap
- FAISS provides O(log n) vector search — scales to millions of chunks
- Keyword fallback works well up to ~10K chunks
- Files > `MAX_FILE_SIZE_MB` are skipped (configurable)

### Scaling
- Add more Uvicorn workers: `--workers 4` in Dockerfile CMD
- Use a persistent vector DB (Milvus/Pinecone) for very large corpora
- Pre-build FAISS index offline and mount as volume

### Memory
- Each chunk is ~1KB text; 100K chunks ≈ 100MB RAM for index
- Parquet/Excel files are loaded into pandas then freed after parsing

---

## 🧩 Project Structure

```
copilot-analyst/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── api/                 # chat.py, files.py, health.py
│   │   ├── agents/              # orchestrator.py (plan→retrieve→synthesize)
│   │   ├── core/                # config.py, models.py, logging.py
│   │   ├── parsers/             # file_parser.py (multi-format)
│   │   └── services/            # index_service.py, file_source.py, llm_provider.py
│   ├── tests/                   # test_app.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/          # ChatPanel, MessageBubble, Sidebar, FilesPanel
│   │   ├── stores/              # appStore.ts (Zustand)
│   │   ├── types/               # index.ts
│   │   └── utils/               # api.ts (SSE streaming)
│   ├── package.json
│   └── Dockerfile
├── sample-data/                 # CSV, JSON, XLSX, Parquet, ZIP samples
├── scripts/run-local.sh
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| Backend starts but returns mock responses | Add an API key to `.env` and set `LLM_PROVIDER` |
| "No files indexed" | Check `LOCAL_FILES_PATH` points to correct folder |
| S3 access denied | Verify `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, bucket policy |
| Streaming not working | Ensure nginx/proxy doesn't buffer SSE; check `proxy_buffering off` |
| FAISS not available | Install `faiss-cpu`; without it, keyword search is used automatically |
| Large file OOM | Reduce `MAX_FILE_SIZE_MB` or increase Docker memory limit |
| CORS error | Add frontend URL to `CORS_ORIGINS` in `.env` |

---

## 🛡 Security

- File path traversal is blocked (paths are resolved against base directory)
- All credentials via env vars — never hardcoded
- Input sanitization in chat endpoint
- File size limits to prevent OOM attacks
- S3 paths are read-only (no write operations)
