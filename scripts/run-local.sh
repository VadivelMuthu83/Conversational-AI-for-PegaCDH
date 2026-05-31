#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
#  Copilot Analyst — Mac/Linux Run Script
#  Usage: bash scripts/run-local.sh
# ═══════════════════════════════════════════════════════
set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo -e "${BLUE}══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Copilot Analyst — Pega CDH Edition${NC}"
echo -e "${BLUE}══════════════════════════════════════════════${NC}"

# ── Prerequisites ────────────────────────────────────────
for tool in python3 node npm; do
  if ! command -v "$tool" &>/dev/null; then
    echo -e "${RED}✗ $tool not found${NC}"; exit 1
  fi
done
echo -e "${GREEN}✓ Python $(python3 --version | cut -d' ' -f2)${NC}"
echo -e "${GREEN}✓ Node $(node --version)${NC}"

# ── .env ─────────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  echo -e "${YELLOW}⚠  Created .env — add your API key then re-run${NC}"
  exit 0
fi
if grep -q "your_key_here" .env; then
  echo -e "${RED}✗ .env has placeholder key — add real API key first${NC}"; exit 1
fi

# ── Backend ──────────────────────────────────────────────
echo -e "\n${GREEN}[1/4] Setting up Python virtual environment...${NC}"
cd backend
[ ! -d venv ] && python3 -m venv venv
source venv/bin/activate

echo -e "${GREEN}[2/4] Installing dependencies...${NC}"
python install.py

cp ../.env .env 2>/dev/null || true

echo -e "${GREEN}[3/4] Starting backend...${NC}"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Wait for backend ready
echo -n "  Waiting for backend"
for i in {1..30}; do
  sleep 2
  if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    echo -e " ${GREEN}ready!${NC}"; break
  fi
  echo -n ".";
done

# ── Frontend ─────────────────────────────────────────────
echo -e "${GREEN}[4/4] Starting frontend...${NC}"
cd frontend
[ ! -d node_modules ] && npm install
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${BLUE}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅  Frontend → http://localhost:3000${NC}"
echo -e "${GREEN}✅  Backend  → http://localhost:8000${NC}"
echo -e "${GREEN}✅  API Docs → http://localhost:8000/docs${NC}"
echo -e "${BLUE}══════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Ctrl+C to stop both services${NC}"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
