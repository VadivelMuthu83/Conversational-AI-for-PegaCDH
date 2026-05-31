@echo off
REM ═══════════════════════════════════════════════════════
REM  Copilot Analyst — Windows Setup Script
REM  Run from the project root: scripts\setup-windows.bat
REM ═══════════════════════════════════════════════════════
setlocal EnableDelayedExpansion

echo.
echo ══════════════════════════════════════════════
echo   Copilot Analyst — Windows Setup
echo ══════════════════════════════════════════════

REM ── Check Python ────────────────────────────────────────
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found.
    echo Install Python 3.10+ from https://python.org
    echo Make sure to check "Add Python to PATH" during install.
    pause & exit /b 1
)
FOR /F "tokens=2" %%i IN ('python --version 2^>^&1') DO SET PYVER=%%i
echo [OK] Python %PYVER% found

REM ── Check Node ──────────────────────────────────────────
node --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Node.js not found.
    echo Install Node.js 18+ from https://nodejs.org
    pause & exit /b 1
)
FOR /F %%i IN ('node --version') DO SET NODEVER=%%i
echo [OK] Node.js %NODEVER% found

REM ── .env setup ──────────────────────────────────────────
IF NOT EXIST .env (
    echo.
    echo Copying .env.example to .env...
    copy .env.example .env >nul
    echo.
    echo IMPORTANT: Open .env in Notepad and set your API key:
    echo   LLM_PROVIDER=anthropic
    echo   ANTHROPIC_API_KEY=sk-ant-your-real-key-here
    echo.
    echo Then run this script again.
    notepad .env
    pause & exit /b 0
)

REM Check if placeholder key is still there
findstr /C:"your_key_here" .env >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo.
    echo ERROR: .env still has placeholder API key.
    echo Open .env and replace "your_key_here" with your real API key.
    notepad .env
    pause & exit /b 1
)
echo [OK] .env configured

REM ── Backend setup ───────────────────────────────────────
echo.
echo [1/4] Creating Python virtual environment...
cd backend
IF NOT EXIST venv (
    python -m venv venv
    echo [OK] Virtual environment created
) ELSE (
    echo [OK] Virtual environment already exists
)

echo.
echo [2/4] Installing Python dependencies...
echo This may take 5-10 minutes on first run (downloads PyTorch ~800MB)
echo.
call venv\Scripts\activate.bat
REM Use install.py which handles Windows-specific torch install
python install.py
IF %ERRORLEVEL% NEQ 0 (
    echo WARNING: Some packages may have failed. Continuing...
)

REM Copy .env into backend
copy .\..\env .env >nul 2>&1
copy .\..\env.env .env >nul 2>&1

REM ── Start backend in new window ──────────────────────────
echo.
echo [3/4] Starting backend on port 8000...
start "Copilot Analyst - Backend" cmd /k "cd /d %CD% && venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"
cd ..

REM Wait for backend to start
echo Waiting for backend to start...
timeout /t 8 /nobreak >nul

REM ── Frontend setup ──────────────────────────────────────
echo.
echo [4/4] Setting up and starting frontend...
cd frontend

IF NOT EXIST node_modules (
    echo Installing npm packages...
    npm install
) ELSE (
    echo [OK] node_modules already installed
)

IF NOT EXIST .env.local (
    copy .env.example .env.local >nul 2>&1
)

start "Copilot Analyst - Frontend" cmd /k "cd /d %CD% && npm run dev"
cd ..

REM ── Done ────────────────────────────────────────────────
echo.
echo ══════════════════════════════════════════════
echo   SETUP COMPLETE
echo.
echo   Frontend  ^>  http://localhost:3000
echo   Backend   ^>  http://localhost:8000
echo   API Docs  ^>  http://localhost:8000/docs
echo.
echo   Two windows opened for backend and frontend.
echo   Close them to stop the application.
echo ══════════════════════════════════════════════
echo.
echo Press any key to run API verification tests...
pause >nul

REM Quick health check
echo.
echo Running health check...
curl -sf http://localhost:8000/api/health
IF %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Backend is healthy!
) ELSE (
    echo.
    echo Backend not responding yet - it may still be starting up.
    echo Check the backend window for errors.
)
pause
