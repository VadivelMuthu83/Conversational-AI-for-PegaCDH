# Windows Installation Guide — Python 3.13

## What went wrong and why

Your machine has **Python 3.13**. The original `requirements.txt` pinned versions
that predate Python 3.13 and have no pre-built Windows wheels for it:

| Package | Was pinned | Problem | Fixed to |
|---------|-----------|---------|----------|
| `pyarrow` | 14.0.2 / 17.0.0 | No py313 wheel | 24.0.0 |
| `torch` | 2.4.1 | No py313 wheel | 2.7.0 (CPU) |
| `openai` | 1.55.0 | Old API | 2.38.0 |
| `langsmith` | 0.1.147 | Old API | 0.8.7 |
| `fastapi` | 0.115.0 | Old | 0.136.3 |

All are fixed in this ZIP.

---

## Clean install — exact steps

Open **Command Prompt** (not PowerShell, not Git Bash).

```cmd
REM 1. Enter project folder
cd C:\Users\vadiv\Downloads\copilot-analyst-windows-fix\copilot-analyst

REM 2. Set up .env (do this once)
copy .env.example .env
notepad .env
```

In Notepad, set your API key and save:
```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-real-key-here
KNOWLEDGE_PATH=./sample-data
RAG_STORE_PATH=./index
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

```cmd
REM 3. Enter backend folder
cd backend

REM 4. Create fresh virtual environment
python -m venv venv

REM 5. Activate it
venv\Scripts\activate

REM 6. Run the installer (handles torch + all packages correctly for Python 3.13)
python install.py
```

You will see output like:
```
[1/4] Upgrading pip, setuptools, wheel ...  ✓ Done
[2/4] Installing PyTorch (CPU) ...          ✓ Done
[3/4] Installing requirements.txt ...       ✓ Done
[4/4] Verifying imports ...
  ✓  FastAPI
  ✓  Pandas
  ✓  PyArrow
  ✓  SentenceTransformers
  ✓  FAISS
  ...
✅  All dependencies installed successfully!
```

```cmd
REM 7. Copy .env into backend folder
copy ..\.env .env

REM 8. Start backend
uvicorn app.main:app --reload --port 8000
```

**New terminal window:**
```cmd
cd C:\Users\vadiv\Downloads\copilot-analyst-windows-fix\copilot-analyst\frontend
npm install
npm run dev
```

Open browser: **http://localhost:3000**

---

## Verify it works

```cmd
curl http://localhost:8000/api/health
```

Expected:
```json
{"status":"ok","llm_provider":"anthropic","indexed_files":9,"indexed_chunks":187}
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `pkg_resources` not found | Run `pip install --upgrade setuptools` first |
| `pyarrow` build fails | Delete venv, re-run `python install.py` from the new ZIP |
| `torch==2.4.1` not found | Fixed — now uses 2.7.0 which supports Python 3.13 |
| `uvicorn` not found | Make sure venv is activated: `venv\Scripts\activate` |
| `No module named 'app'` | Run uvicorn from inside `backend\` folder, not project root |
| Port 8000 in use | `netstat -ano \| findstr :8000` → `taskkill /PID <number> /F` |
| Frontend uuid warning | Fixed — now uses uuid@11 |

---

## Check your Python version

```cmd
python --version
```

Must be **3.10, 3.11, 3.12, or 3.13**. All are supported now.
