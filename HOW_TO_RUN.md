# How to Run Copilot Analyst on Windows

---

## Before you start — understand the folder structure

After unzipping you have this layout:

```
copilot-analyst-py313-fix\
  copilot-analyst\              ← project root
    backend\                    ← Python backend (run uvicorn from here)
      app\
      install.py
      requirements.txt
    frontend\                   ← React frontend
    sample-data\                ← data files the app reads
      sales.csv
      customers.json
      knowledge\
        NBA_Strategy_Guide.md
        ...
    .env.example
```

The `backend\` and `sample-data\` folders are **siblings** — both directly inside `copilot-analyst\`.

---

## Step 1 — Open Command Prompt in the right folder

Press `Win + R`, type `cmd`, press Enter.

Then navigate to the **backend** folder:

```cmd
cd C:\Users\vadiv\Downloads\copilot-analyst-py313-fix\copilot-analyst\backend
```

Confirm you are in the right place:
```cmd
dir
```
You should see `app\`, `install.py`, `requirements.txt`, `venv\` listed.

---

## Step 2 — Create the .env file (first time only)

Go up one level to the project root, copy the template, then go back:

```cmd
cd ..
copy .env.example .env
notepad .env
```

In Notepad make **exactly these changes** then save:

**Line 1 — your API key:**
```
ANTHROPIC_API_KEY=sk-ant-api03-your-real-key-here
```

**Line 2 — the path to sample-data (use YOUR actual Windows path):**
```
KNOWLEDGE_PATH=C:\Users\vadiv\Downloads\copilot-analyst-py313-fix\copilot-analyst\sample-data
```

> ⚠️ **This is the most common cause of `indexed_files: 0`.**
> The path must point to the `sample-data` folder that contains `sales.csv`, `customers.json` etc.
> Use the absolute path (starting with `C:\`) — not a relative path.

Save and close Notepad.

---

## Step 3 — Install dependencies (first time only)

```cmd
cd backend
python -m venv venv
venv\Scripts\activate
python install.py
```

Wait for:
```
✅  All dependencies installed successfully!
```

This takes 5–10 minutes first time (downloads PyTorch ~800MB).

---

## Step 4 — Copy .env into backend folder

```cmd
copy ..\.env .env
```

Confirm the path is correct:
```cmd
type .env | findstr KNOWLEDGE_PATH
```
You should see your absolute path like:
```
KNOWLEDGE_PATH=C:\Users\vadiv\Downloads\copilot-analyst-py313-fix\copilot-analyst\sample-data
```

---

## Step 5 — Start the backend

Make sure you are in `backend\` with venv active:
```cmd
cd C:\Users\vadiv\Downloads\copilot-analyst-py313-fix\copilot-analyst\backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Watch the startup logs. You should see lines like:
```
INFO | Files path  : C:\Users\vadiv\...\sample-data
INFO | Path exists : True
INFO | Indexing 9 files ...
INFO | Index built: 187 chunks
INFO | ✅ Startup complete — 9 files, 187 chunks
INFO | Application startup complete.
```

**If you see `Path exists : False`** — the KNOWLEDGE_PATH in your .env is wrong. Stop, fix it, restart.

**Keep this window open.**

---

## Step 6 — Start the frontend (new Command Prompt window)

Open a **second** Command Prompt window:

```cmd
cd C:\Users\vadiv\Downloads\copilot-analyst-py313-fix\copilot-analyst\frontend
npm install
npm run dev
```

Wait for:
```
  ➜  Local:   http://localhost:3000/
```

**Keep this window open.**

---

## Step 7 — Verify it works

In **PowerShell** (or a third Command Prompt):

```powershell
curl http://localhost:8000/api/health -UseBasicParsing
```

You should see:
```json
{
  "status": "ok",
  "llm_provider": "anthropic",
  "indexed_files": 9,
  "indexed_chunks": 187,
  "files_path_exists": true
}
```

✅ `indexed_files: 9` — all sample files found  
✅ `files_path_exists: true` — path resolved correctly  

If `indexed_files` is still 0, run this to see the exact path the app is using:

```powershell
curl http://localhost:8000/ -UseBasicParsing
```

Look at `files_path_abs` in the response — that is the exact folder the app is reading from. Check that folder exists and contains CSV/JSON files.

---

## Step 8 — Fix indexed_files: 0 (if still happening)

**Option A — Trigger a manual re-index:**

```powershell
Invoke-RestMethod -Method POST http://localhost:8000/api/files/refresh
```

This will show:
```json
{"status": "refreshed", "files_parsed": 9, "files_path_abs": "C:\...\sample-data"}
```

**Option B — Check what path the app is actually reading:**

```powershell
curl http://localhost:8000/api/files -UseBasicParsing
```

This shows `path_abs` — the resolved absolute path. If it is wrong, fix `KNOWLEDGE_PATH` in `backend\.env`.

**Option C — Set the absolute path directly in backend\.env:**

Open `backend\.env` and change:
```
KNOWLEDGE_PATH=C:\Users\vadiv\Downloads\copilot-analyst-py313-fix\copilot-analyst\sample-data
```
Then restart uvicorn (Ctrl+C, then run uvicorn again).

---

## Step 9 — Open the app and chat

Go to **http://localhost:3000** in your browser.

Try these queries:
```
What files are indexed and what do they contain?
Which products have the highest profit margin?
Summarise all sales data by region
How does arbitration priority work in Pega CDH?
What AUC threshold should ADM models meet?
```

---

## Next time — two commands to start

**Terminal 1 (backend):**
```cmd
cd C:\Users\vadiv\Downloads\copilot-analyst-py313-fix\copilot-analyst\backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 (frontend):**
```cmd
cd C:\Users\vadiv\Downloads\copilot-analyst-py313-fix\copilot-analyst\frontend
npm run dev
```

---

## Common errors

| What you see | Cause | Fix |
|---|---|---|
| `indexed_files: 0` | KNOWLEDGE_PATH wrong | Use absolute path in backend\.env |
| `Path exists: False` in startup log | Path doesn't exist | Check KNOWLEDGE_PATH spelling |
| `Application startup complete` but no files | .env not copied to backend\ | Run `copy ..\.env .env` inside backend\ |
| `ModuleNotFoundError` | venv not activated | Run `venv\Scripts\activate` first |
| `address already in use` | Port 8000 busy | `netstat -ano \| findstr :8000` → `taskkill /PID <num> /F` |
| PowerShell security warning on curl | Windows curl is Invoke-WebRequest | Add `-UseBasicParsing` flag |

