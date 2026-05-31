#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
#  Copilot Analyst — API Test Script
#  Runs all checks against a running backend.
#  Usage: bash scripts/test-api.sh [host]
#  Default host: http://localhost:8000
# ═══════════════════════════════════════════════════════
HOST="${1:-http://localhost:8000}"
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
PASS=0; FAIL=0

check() {
  local name="$1"; local url="$2"; local expected="$3"
  local result
  result=$(curl -sf "$url" 2>/dev/null) || { echo -e "${RED}✗ $name — connection failed${NC}"; ((FAIL++)); return; }
  if echo "$result" | grep -q "$expected"; then
    echo -e "${GREEN}✓ $name${NC}"
    ((PASS++))
  else
    echo -e "${RED}✗ $name — expected '$expected' not found${NC}"
    echo "  Response: $(echo "$result" | head -c 200)"
    ((FAIL++))
  fi
}

post_check() {
  local name="$1"; local url="$2"; local body="$3"; local expected="$4"
  local result
  result=$(curl -sf -X POST "$url" -H "Content-Type: application/json" -d "$body" 2>/dev/null) || {
    echo -e "${RED}✗ $name — connection failed${NC}"; ((FAIL++)); return
  }
  if echo "$result" | grep -q "$expected"; then
    echo -e "${GREEN}✓ $name${NC}"
    ((PASS++))
  else
    echo -e "${RED}✗ $name — expected '$expected' not found${NC}"
    echo "  Response: $(echo "$result" | head -c 300)"
    ((FAIL++))
  fi
}

echo -e "${BLUE}══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Copilot Analyst API Tests — $HOST${NC}"
echo -e "${BLUE}══════════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}── Core endpoints ─────────────────────────${NC}"
check "Root endpoint"             "$HOST/"                        '"cdh_mode":true'
check "Health check"              "$HOST/api/health"              '"status":"ok"'
check "Files indexed"             "$HOST/api/files/indexed"       '"total_files"'
check "Files list"                "$HOST/api/files"               '"total"'
check "Observability status"      "$HOST/api/observability/status" '"rag_enabled"'
check "Polaris status (disabled)" "$HOST/api/polaris/status"      '"enabled"'

echo ""
echo -e "${YELLOW}── CDH endpoints ──────────────────────────${NC}"
check "CDH sources"          "$HOST/api/cdh/sources"           '"total_indexed"'
check "CDH knowledge articles" "$HOST/api/cdh/knowledge-articles" '"total_articles"'
check "CDH templates"        "$HOST/api/cdh/templates"         '"templates"'

echo ""
echo -e "${YELLOW}── Chat endpoints (sync mode) ─────────────${NC}"
post_check "Generic chat" \
  "$HOST/api/chat" \
  '{"message":"What files are available?","stream":false}' \
  '"content"'

post_check "CDH chat" \
  "$HOST/api/cdh/chat" \
  '{"message":"What CDH data sources are indexed?","stream":false}' \
  '"content"'

post_check "CDH chat kb_only" \
  "$HOST/api/cdh/chat" \
  '{"message":"How should I configure ADM models?","stream":false,"kb_only":true}' \
  '"content"'

echo ""
echo -e "${YELLOW}── Index management ───────────────────────${NC}"
post_check "File refresh" \
  "$HOST/api/files/refresh" \
  '{}' \
  '"status":"refreshed"'

echo ""
echo -e "${BLUE}══════════════════════════════════════════════${NC}"
if [ $FAIL -eq 0 ]; then
  echo -e "${GREEN}  All $PASS tests passed ✓${NC}"
else
  echo -e "${RED}  $FAIL failed, $PASS passed${NC}"
  exit 1
fi
echo -e "${BLUE}══════════════════════════════════════════════${NC}"
