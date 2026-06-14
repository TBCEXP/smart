#!/usr/bin/env bash
# 真实 API 环境下跑 Phase 1.5 试点（MX 默认，CO 加 --co）
# 用法: bash scripts/pilot_live.sh [BASE_URL] [--co]
set -euo pipefail

BASE="http://127.0.0.1:8000"
COUNTRY="MX"
PILOT_PATH="mx"

for arg in "$@"; do
  case "$arg" in
    --co) COUNTRY="CO"; PILOT_PATH="co" ;;
    http*) BASE="$arg" ;;
  esac
done

echo "=== SMART CRM Live Pilot ($COUNTRY) ==="
echo "Base: $BASE"
echo ""

echo "[1] 检查 API 就绪"
PROBE=$(curl -sf -X POST "$BASE/api/integrations/probe")
LIVE=$(echo "$PROBE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('summary',{}).get('live_ok',0))" 2>/dev/null || echo 0)
echo "$PROBE" | python3 -m json.tool 2>/dev/null | head -40 || echo "$PROBE"

if [ "$LIVE" -lt 4 ]; then
  echo ""
  echo "⚠ 仅 $LIVE/4 项 live API 通过。可在 Mock 模式继续试跑，但产出质量仅供演示。"
  echo "  请在 Tab2 配置: Exa + Firecrawl + OpenAI + 飞书 后重试。"
  sleep 3
fi

echo ""
echo "[2] 启动 $COUNTRY 试点 (Track B → Brainstorm → 入队)"
PILOT=$(curl -sf -X POST "$BASE/api/pilot/$PILOT_PATH/start" \
  -H "Content-Type: application/json" \
  -d "{\"country_iso\":\"$COUNTRY\",\"category_l3\":\"bakeware\",\"anchor_limit\":2,\"leads_per_task\":5,\"enqueue_track_a\":true}")
echo "$PILOT" | python3 -m json.tool 2>/dev/null || echo "$PILOT"
SESSION_ID=$(echo "$PILOT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null || echo "")

echo ""
echo "[3] 执行 1 条到期 Track A 任务（5 条线索）"
DUE=$(curl -sf -X POST "$BASE/api/schedules/run-due?limit=1&count_per_task=5")
echo "$DUE" | python3 -m json.tool 2>/dev/null || echo "$DUE"
BATCH_ID=$(echo "$DUE" | python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('jobs') or [{}])[0].get('batch_id',''))" 2>/dev/null || echo "")

if [ -n "$BATCH_ID" ]; then
  echo ""
  echo "[4] 等待批次完成 (SSE)…"
  curl -sf -N --max-time 120 "$BASE/api/stream/$BATCH_ID" > /dev/null 2>&1 || true
  BATCH=$(curl -sf "$BASE/api/batch/$BATCH_ID")
  COUNT=$(echo "$BATCH" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('leads',[])))" 2>/dev/null || echo 0)
  echo "  产出线索: $COUNT 条"
  LEAD_ID=$(echo "$BATCH" | python3 -c "import sys,json; ls=json.load(sys.stdin).get('leads',[]); print(ls[0]['id'] if ls else '')" 2>/dev/null || echo "")
  if [ -n "$LEAD_ID" ]; then
    echo ""
    echo "[5] 确认 1 条线索入库飞书 (review→confirm)"
    CONF=$(curl -sf -X POST "$BASE/api/confirm/$LEAD_ID" || echo '{"error":"confirm failed"}')
    echo "$CONF" | python3 -m json.tool 2>/dev/null || echo "$CONF"
  fi
else
  echo "  无到期任务（请 Tab4 查看定时任务）"
fi

echo ""
echo "=== Live Pilot ($COUNTRY) 完成 ==="
echo "  session_id: $SESSION_ID"
echo "  batch_id:   $BATCH_ID"
