# Copilot Analyst — Quick Start Guide

Supports: Google Gemini (free) · OpenAI · Azure OpenAI · Anthropic Claude

---

## Prerequisites

| Tool | Check | Install |
|------|-------|---------|
| Python 3.10+ | `python --version` | https://python.org |
| Node.js 18+ | `node --version` | https://nodejs.org |
| Git (optional) | `git --version` | https://git-scm.com |

---

## Step 1 — Configure your API key

Go to the `backend\` folder and rename `.env.template` to `.env`:

```cmd
cd backend
copy .env.template .env
notepad .env
```

Make **two changes** then save:

**1. Paste your API key** (choose one provider — Gemini is free):

```
# Gemini (free)
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy-your-key-here

# OR OpenAI
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-your-key-here

# OR Azure OpenAI
# LLM_PROVIDER=azure
# AZURE_OPENAI_API_KEY=your-key
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# AZURE_OPENAI_DEPLOYMENT=gpt-4o

# OR Anthropic
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**2. Paste the full path to your sample-data folder:**

```
KNOWLEDGE_PATH=C:\Users\vadiv\Downloads\SmartAnalysis\SmartAnalysis\sample-data
```

---

## Step 2 — Install backend (one time only)

```cmd
cd backend
python -m venv venv
venv\Scripts\activate
python install.py
```

Takes 5–15 min first run (downloads PyTorch). Wait for:
```
✅  All dependencies installed successfully!
```

---

## Step 3 — Start the application

**Terminal 1 — backend:**
```cmd
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Wait for: `Application startup complete.`

Watch for these lines confirming your key loaded:
```
  GEMINI key     : ✅ SET
  Files path     : C:\...\sample-data
  Path exists    : True
```

**Terminal 2 — frontend (new window):**
```cmd
cd frontend
npm install
npm run dev
```

Wait for: `➜  Local: http://localhost:3000/`

---

## Step 4 — Open the app

Go to **http://localhost:3000**

---

## Step 5 — Verify everything works

```powershell
Invoke-RestMethod http://localhost:8000/api/health | ConvertTo-Json
```

Must show:
- `"status": "ok"`
- `"indexed_files"` > 0
- `"files_path_exists": true`

---

## Test queries

```
What files are indexed and what do they contain?
Which products have the highest profit margin?
What is the arbitration priority formula in Pega CDH?
What AUC score means an ADM model is failing?
How does Impact Analyzer predict revenue changes?
What are the Value Finder quadrants?
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Demo mode / no LLM response | API key not in `backend\.env` — file must be in backend folder |
| `indexed_files: 0` | Set `KNOWLEDGE_PATH` to full absolute path in `backend\.env` |
| `gemini-1.5-pro not found` | Change to `GEMINI_MODEL=gemini-2.0-flash` in `backend\.env` |
| `ModuleNotFoundError: app` | Run uvicorn from inside `backend\` folder |
| Port 8000 in use | `netstat -ano \| findstr :8000` then `taskkill /PID <num> /F` |
| `venv\Scripts\activate` blocked | Use cmd.exe not PowerShell, or run `Set-ExecutionPolicy RemoteSigned` |
| Slow first start | Embedding model downloads ~80MB once — normal |

---

## Next time (no reinstall needed)

```cmd
cd backend && venv\Scripts\activate && uvicorn app.main:app --reload --port 8000
```
```cmd
cd frontend && npm run dev
```
