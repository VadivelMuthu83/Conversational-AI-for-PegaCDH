# Copilot Analyst — VS Code Setup and GitHub Publishing Guide

---

## Part 1 — Install Required Tools

### 1.1 Install VS Code
Download from: https://code.visualstudio.com
Accept all defaults during installation.

### 1.2 Install VS Code Extensions

Open VS Code. Press `Ctrl+Shift+X` to open Extensions panel.
Search and install each of these:

| Extension | Publisher | Purpose |
|-----------|-----------|---------|
| Python | Microsoft | Python language support, debugging |
| Pylance | Microsoft | Python IntelliSense |
| ESLint | Microsoft | JavaScript/TypeScript linting |
| Prettier | Prettier | Code formatting |
| GitLens | GitKraken | Enhanced Git history and blame |
| REST Client | Humao | Test API endpoints inside VS Code |
| Thunder Client | Rangav | Alternative API tester (easier UI) |
| dotenv | mikestead | Syntax highlighting for .env files |

After installing, **restart VS Code**.

---

## Part 2 — Open the Project in VS Code

### 2.1 Extract the ZIP

Extract `copilot-analyst-py313-fix.zip` to a folder you can remember.

Recommended location:
```
C:\Projects\copilot-analyst
```

So your folder structure looks like:
```
C:\Projects\copilot-analyst\
  backend\
  frontend\
  sample-data\
  .env.example
  START_HERE.md
```

### 2.2 Open in VS Code

**Option A — From VS Code menu:**
- Open VS Code
- Click `File` → `Open Folder`
- Navigate to `C:\Projects\copilot-analyst`
- Click `Select Folder`

**Option B — From Command Prompt:**
```
cd C:\Projects\copilot-analyst
code .
```

VS Code opens with the full project visible in the Explorer panel on the left.

---

## Part 3 — Configure the Project

### 3.1 Create the .env File

In VS Code Explorer panel (left side):
- Right-click `.env.example`
- Click `Copy`
- Right-click in empty space in Explorer panel
- Click `Paste`
- Rename the pasted file from `.env.example copy` to `.env`

Click on `.env` to open it. Make **two changes**:

**Change 1 — your API key:**
```
ANTHROPIC_API_KEY=sk-ant-api03-your-real-key-here
```

**Change 2 — absolute path to sample-data:**
```
KNOWLEDGE_PATH=C:\Projects\copilot-analyst\sample-data
```

Press `Ctrl+S` to save.

### 3.2 Configure VS Code Python Interpreter

Press `Ctrl+Shift+P` → type `Python: Select Interpreter` → press Enter.

You will see a list of Python installations. Select the one showing:
```
Python 3.13.x  ('venv': venv)
```

If the venv does not appear yet (because you haven't created it),
select any Python 3.10+ interpreter for now — you'll fix this after
creating the venv in Part 4.

### 3.3 Create VS Code Launch Configuration

In VS Code Explorer, create a new folder called `.vscode` at the project root.
Inside it, create a file called `launch.json`.

Click `New Folder` icon in Explorer → name it `.vscode`
Then click `New File` inside `.vscode` → name it `launch.json`

Paste this content:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Backend — FastAPI",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:app",
        "--reload",
        "--port",
        "8000"
      ],
      "cwd": "${workspaceFolder}/backend",
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal",
      "justMyCode": true
    },
    {
      "name": "Backend — Run Tests",
      "type": "debugpy",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/", "-v", "--tb=short"],
      "cwd": "${workspaceFolder}/backend",
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal"
    }
  ]
}
```

Press `Ctrl+S` to save.

### 3.4 Create VS Code Settings

Inside the `.vscode` folder, create `settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/backend/venv/Scripts/python.exe",
  "python.terminal.activateEnvironment": true,
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "[python]": {
    "editor.defaultFormatter": "ms-python.python"
  },
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests/"],
  "python.testing.cwd": "${workspaceFolder}/backend",
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    "**/venv": true,
    "**/node_modules": true
  },
  "terminal.integrated.cwd": "${workspaceFolder}"
}
```

Press `Ctrl+S` to save.

---

## Part 4 — Install Dependencies

### 4.1 Open VS Code Integrated Terminal

Press `` Ctrl+` `` (backtick key, top-left of keyboard) to open the terminal.

The terminal opens at the project root `C:\Projects\copilot-analyst`.

### 4.2 Install Backend Dependencies

In the terminal:

```bash
cd backend
python -m venv venv
venv\Scripts\activate
python install.py
```

Wait for:
```
✅  All dependencies installed successfully!
```

This takes 5–15 minutes first time (downloads PyTorch).

After it finishes, copy .env into the backend folder:
```bash
copy ..\.env .env
```

### 4.3 Select the New venv as Python Interpreter

Now that the venv exists, tell VS Code to use it:

Press `Ctrl+Shift+P` → `Python: Select Interpreter` → Enter

Select:
```
Python 3.13.x  ('venv': venv)  C:\Projects\copilot-analyst\backend\venv\Scripts\python.exe
```

### 4.4 Install Frontend Dependencies

Click the `+` button in the terminal panel to open a **second terminal tab**.

```bash
cd frontend
npm install
```

Wait for `added N packages`.

---

## Part 5 — Run the Application from VS Code

### Method A — Using the Run Panel (recommended for debugging)

**Start the backend with debugging:**

1. Press `F5` or click the **Run and Debug** icon in the left sidebar (triangle with bug)
2. In the dropdown at the top, select `Backend — FastAPI`
3. Click the green **▶ Play** button

The VS Code integrated terminal shows the backend logs:
```
INFO | Files path  : C:\Projects\copilot-analyst\sample-data
INFO | Path exists : True
INFO | Indexing 26 files ...
INFO | Application startup complete.
```

You can now set **breakpoints** by clicking to the left of any line number
in any Python file. The debugger will pause there when that code runs.

**Start the frontend:**

Open a second terminal tab (click `+` in terminal panel):
```bash
cd frontend
npm run dev
```

### Method B — Using Split Terminals

Press `` Ctrl+` `` to open terminal.

**Terminal 1 (backend):**
```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Click the **Split Terminal** icon (two rectangles) in the terminal panel
to open Terminal 2 side by side.

**Terminal 2 (frontend):**
```bash
cd frontend
npm run dev
```

### Open the App

Go to **http://localhost:3000** in your browser.

Look for the green dot in the sidebar — **"Backend connected"**.

---

## Part 6 — Run Tests from VS Code

### Method A — Test Explorer (visual)

1. Click the **beaker icon** in the left sidebar (Testing panel)
2. VS Code discovers tests automatically from `backend/tests/`
3. Click **Run All Tests** (double triangle icon at top of Testing panel)
4. Green ticks = pass, red crosses = fail
5. Click any test to see its output

### Method B — Terminal

In a terminal with venv active:
```bash
cd backend
pytest tests/ -v
```

Expected result:
```
35 passed in 18.4s
```

---

## Part 7 — Test API Endpoints in VS Code

Create a file called `api-tests.http` in the project root.

Click `New File` in Explorer → name it `api-tests.http`

Paste this content:

```http
### Health check
GET http://localhost:8000/api/health

###
### List indexed files
GET http://localhost:8000/api/files/indexed

###
### List CDH knowledge articles
GET http://localhost:8000/api/cdh/knowledge-articles

###
### CDH sources detected
GET http://localhost:8000/api/cdh/sources

###
### Chat — basic query (sync mode)
POST http://localhost:8000/api/chat
Content-Type: application/json

{
  "message": "What files are indexed and what do they contain?",
  "stream": false
}

###
### CDH chat — arbitration question
POST http://localhost:8000/api/cdh/chat
Content-Type: application/json

{
  "message": "What is the arbitration priority formula in Pega CDH?",
  "stream": false
}

###
### CDH chat — ADM models question
POST http://localhost:8000/api/cdh/chat
Content-Type: application/json

{
  "message": "What AUC score means an ADM model is failing?",
  "stream": false
}

###
### CDH chat — knowledge articles only
POST http://localhost:8000/api/cdh/chat
Content-Type: application/json

{
  "message": "How does Impact Analyzer simulate strategy changes?",
  "stream": false,
  "kb_only": true
}

###
### Refresh index (re-scan all files)
POST http://localhost:8000/api/files/refresh

###
### Document generation
POST http://localhost:8000/api/cdh/generate-document
Content-Type: application/json

{
  "question": "Explain ADM model health assessment procedures",
  "doc_type": "adm_health_report"
}

###
### Observability status
GET http://localhost:8000/api/observability/status
```

**To run a request:**
- Click `Send Request` that appears above each `###` block
- The response appears in a panel on the right

> Requires the **REST Client** extension (installed in Part 1).

---

## Part 8 — Publish to GitHub

### 8.1 Install Git

Check if Git is installed:
```bash
git --version
```

If not installed: download from https://git-scm.com
Accept all defaults. Restart VS Code after installing.

### 8.2 Create a GitHub Account and Repository

1. Go to **https://github.com** and sign in (or create a free account)
2. Click the `+` icon in the top-right corner
3. Click `New repository`
4. Fill in:
   - **Repository name:** `copilot-analyst`
   - **Description:** `Pega CDH AI chat analyst — RAG + LangSmith + Knowledge Articles`
   - **Visibility:** Private (recommended — your .env must not be public)
   - **Do NOT check** "Add a README file" (you already have one)
5. Click `Create repository`
6. Copy the URL shown — it looks like: `https://github.com/YOUR-USERNAME/copilot-analyst.git`

### 8.3 Create .gitignore

In VS Code Explorer, create a new file at the project root called `.gitignore`.

Paste this content exactly:

```
# Python
backend/venv/
backend/__pycache__/
backend/app/__pycache__/
backend/**/__pycache__/
*.pyc
*.pyo
*.egg-info/

# Environment files — NEVER commit these
.env
backend/.env

# Vector index (large binary files)
backend/index/
*.faiss
*.pkl

# Node
frontend/node_modules/
frontend/dist/
frontend/.env.local
frontend/.env

# VS Code
.vscode/settings.json

# OS
.DS_Store
Thumbs.db
desktop.ini

# Logs
*.log
```

Press `Ctrl+S` to save.

> ⚠️ Critical: `.env` is in `.gitignore`. Your API keys will NOT be uploaded to GitHub.
> Only `.env.example` (which contains no real keys) will be uploaded.

### 8.4 Initialise Git in VS Code

**Method A — VS Code Source Control panel:**

1. Click the **Source Control** icon in the left sidebar (branch icon)
2. Click `Initialize Repository`
3. VS Code initialises git in the project folder

**Method B — Terminal:**
```bash
git init
git branch -M main
```

### 8.5 Stage All Files

**Method A — VS Code Source Control panel:**

1. In the Source Control panel, you see all changed files listed under `Changes`
2. Click the `+` icon next to `Changes` (Stage All Changes)
3. All files move to `Staged Changes`

**Method B — Terminal:**
```bash
git add .
```

**Verify .env is NOT staged:**
```bash
git status
```

Scroll through the output. You must NOT see `.env` or `backend/.env` listed.
If you see them, stop and check your `.gitignore`.

### 8.6 Make the First Commit

**Method A — VS Code Source Control panel:**

1. In the Source Control panel, click the text box at the top that says `Message`
2. Type: `Initial commit — Copilot Analyst with CDH RAG knowledge base`
3. Click the **✓ Commit** button (checkmark icon)

**Method B — Terminal:**
```bash
git commit -m "Initial commit — Copilot Analyst with CDH RAG knowledge base"
```

### 8.7 Connect to GitHub and Push

**Method A — VS Code Source Control panel (easiest):**

1. In Source Control panel, click the `...` menu (three dots)
2. Click `Remote` → `Add Remote`
3. Paste your GitHub repository URL: `https://github.com/YOUR-USERNAME/copilot-analyst.git`
4. Name it `origin`
5. Click `...` again → `Push`
6. VS Code may ask you to sign in to GitHub — click `Allow` and follow the browser prompts

**Method B — Terminal:**
```bash
git remote add origin https://github.com/YOUR-USERNAME/copilot-analyst.git
git push -u origin main
```

GitHub may ask for your username and password (or a Personal Access Token).

**If asked for a token instead of password:**
1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click `Generate new token (classic)`
3. Tick `repo` scope
4. Click `Generate token`
5. Copy the token and paste it as your password

### 8.8 Verify the Upload

1. Go to `https://github.com/YOUR-USERNAME/copilot-analyst` in your browser
2. You should see all your files listed
3. Confirm these files are present: `backend/`, `frontend/`, `sample-data/`, `START_HERE.md`
4. Confirm `.env` is **not** listed (it must not be there)

---

## Part 9 — Add GitHub Actions (Automated Testing)

This automatically runs your tests every time you push code to GitHub.

In VS Code Explorer, create this folder structure:
```
.github/
  workflows/
    ci.yml
```

Paste this into `ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: |
          cd backend
          pip install --upgrade pip setuptools wheel
          pip install torch --index-url https://download.pytorch.org/whl/cpu --only-binary=:all:
          pip install -r requirements.txt --only-binary=pyarrow,faiss-cpu

      - name: Run tests
        run: |
          cd backend
          pytest tests/ -v --tb=short
        env:
          LLM_PROVIDER: anthropic
          FILE_SOURCE: local
          KNOWLEDGE_PATH: ../sample-data
          RAG_ENABLED: "true"
          EMBEDDING_PROVIDER: local
          EMBEDDING_MODEL: all-MiniLM-L6-v2
          RAG_STORE_PATH: ./index
          STREAMING_ENABLED: "true"

  frontend-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install and build
        run: |
          cd frontend
          npm install
          npm run build
```

Save, then commit and push:

**VS Code Source Control panel:**
1. Stage the new files (click `+` next to Changes)
2. Type commit message: `Add GitHub Actions CI workflow`
3. Click Commit → then Push

**Or terminal:**
```bash
git add .github/
git commit -m "Add GitHub Actions CI workflow"
git push
```

After pushing, go to your GitHub repository and click the **Actions** tab.
You will see the CI workflow running. Green tick = all tests passed.

---

## Part 10 — Daily Workflow in VS Code

### Starting the app each day

1. Open VS Code (it remembers your project)
2. Press `` Ctrl+` `` to open terminal
3. Terminal 1 — backend:
   ```bash
   cd backend
   venv\Scripts\activate
   uvicorn app.main:app --reload --port 8000
   ```
4. Split terminal (`+` icon) — Terminal 2 — frontend:
   ```bash
   cd frontend
   npm run dev
   ```
5. Open http://localhost:3000

### Making code changes

1. Edit any Python file in `backend/app/`
2. uvicorn detects the change and **auto-reloads** (you see `Reloading...` in terminal)
3. No need to restart — changes are live immediately
4. Edit any `.tsx` file in `frontend/src/`
5. Vite detects the change and **hot-reloads** the browser automatically

### Saving your work to GitHub

```bash
git add .
git commit -m "describe what you changed"
git push
```

Or use the VS Code Source Control panel:
1. Click Source Control icon
2. Stage changes (`+`)
3. Type message
4. Click Commit → Push

---

## Quick Reference Card

| Task | VS Code | Terminal |
|------|---------|----------|
| Open project | File → Open Folder | `code .` |
| Start backend (with debug) | F5 → Backend — FastAPI | `uvicorn app.main:app --reload --port 8000` |
| Start frontend | New terminal → `npm run dev` | `npm run dev` |
| Run all tests | Testing panel → Run All | `pytest tests/ -v` |
| Test API endpoints | Open api-tests.http → Send Request | `curl http://localhost:8000/api/health` |
| Stage changes | Source Control → `+` | `git add .` |
| Commit | Source Control → type message → ✓ | `git commit -m "message"` |
| Push to GitHub | Source Control → `...` → Push | `git push` |
| Check what's changed | Source Control panel | `git status` |
| View commit history | GitLens sidebar | `git log --oneline` |
