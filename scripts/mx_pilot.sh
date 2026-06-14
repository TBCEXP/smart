#!/usr/bin/env bash
# Phase 1.5 墨西哥试点 CLI — 通过 API 一键跑 Track B → Brainstorm → Track A 入队
# 用法: bash scripts/mx_pilot.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"

echo "=== SMART CRM MX Pilot (Phase 1.5) ==="
echo "Base: $BASE"
echo ""

echo "[1] 当前试点状态"
curl -sf "$BASE/api/pilot/mx/status" | python3 -m json.tool 2>/dev/null || curl -sf "$BASE/api/pilot/mx/status"
echo ""

echo "[2] 启动 MX 试点"
RESULT=$(curl -sf -X POST "$BASE/api/pilot/mx/start" \
  -H "Content-Type: application/json" \
  -d '{
    "city": "CDMX",
    "category_l3": "bakeware",
    "cities": ["CDMX", "Monterrey"],
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
  echo "✓ 试点完成 pilot_id=$PILOT_ID session_id=$SESSION_ID"
  echo ""
  echo "下一步:"
  echo "  1. 打开面板 Tab1，从 Tab4 定时任务选取关键词运行 Track A（每任务 5 条）"
  echo "  2. Tab3 审核开发信 → 确认入库飞书"
  echo "  3. Tab8 为热点产品批量生成 es/en/pt SEO 内容"
else
  echo "✗ 试点失败"
  exit 1
fi
