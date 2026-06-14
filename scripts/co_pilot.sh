#!/usr/bin/env bash
# Phase 1.5 哥伦比亚试点 CLI — Track B → Brainstorm → Track A 入队
# 用法: bash scripts/co_pilot.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"

echo "=== SMART CRM CO Pilot (Phase 1.5) ==="
echo "Base: $BASE"
echo ""

echo "[1] 当前试点状态"
curl -sf "$BASE/api/pilot/co/status" | python3 -m json.tool 2>/dev/null || curl -sf "$BASE/api/pilot/co/status"
echo ""

echo "[2] 启动 CO 试点"
RESULT=$(curl -sf -X POST "$BASE/api/pilot/co/start" \
  -H "Content-Type: application/json" \
  -d '{
    "country_iso": "CO",
    "city": "Bogotá",
    "category_l3": "bakeware",
    "cities": ["Bogotá", "Medellín"],
    "l3_codes": ["bakeware", "cookware-commercial", "flatware"],
    "anchor_limit": 2,
    "leads_per_task": 5,
    "enqueue_track_a": true
  }')
echo "$RESULT" | python3 -m json.tool 2>/dev/null || echo "$RESULT"
echo ""

PILOT_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('pilot_id',''))" 2>/dev/null || echo "")
SESSION_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null || echo "")

if [ -n "$PILOT_ID" ]; then
  echo "✓ CO 试点完成 pilot_id=$PILOT_ID session_id=$SESSION_ID"
  echo ""
  echo "[3] 执行 1 条到期 Track A 任务"
  DUE=$(curl -sf -X POST "$BASE/api/schedules/run-due?limit=1&count_per_task=5" || echo '{}')
  echo "$DUE" | python3 -m json.tool 2>/dev/null || echo "$DUE"
  echo ""
  echo "下一步:"
  echo "  1. Tab4 执行到期任务或 Tab1 手动跑 Track A"
  echo "  2. Tab3 审核西语开发信 → confirm 入库飞书"
  echo "  3. bash scripts/acceptance_report.sh $BASE"
else
  echo "✗ CO 试点失败"
  exit 1
fi
