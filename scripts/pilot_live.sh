#!/usr/bin/env bash
# 真实 API 环境下跑 Phase 1.5 试点（MX 默认，CO 加 --co）
# 用法: bash scripts/pilot_live.sh [BASE_URL] [--co]
# 环境变量:
#   SESSION_TOKEN  — 已有管理会话（跳过 OTP）
#   AUTH_EMAIL     — OTP 登录邮箱（默认 admin@example.com）
#   AUTH_LOG       — OTP 日志路径（默认 /var/lib/smart-crm/auth_emails.log 或 smart-crm/data/auth_emails.log）
set -euo pipefail

BASE="http://127.0.0.1:8000"
COUNTRY="MX"
PILOT_PATH="mx"
AUTH_EMAIL="${AUTH_EMAIL:-admin@example.com}"

for arg in "$@"; do
  case "$arg" in
    --co) COUNTRY="CO"; PILOT_PATH="co" ;;
    http*) BASE="$arg" ;;
  esac
done

get_session_token() {
  if [ -n "${SESSION_TOKEN:-}" ]; then
    echo "$SESSION_TOKEN"
    return
  fi
  local log="${AUTH_LOG:-}"
  if [ -z "$log" ]; then
    for p in /var/lib/smart-crm/auth_emails.log /workspace/smart-crm/data/auth_emails.log ./smart-crm/data/auth_emails.log; do
      [ -f "$p" ] && log="$p" && break
    done
  fi
  curl -sf -X POST "$BASE/api/auth/otp/send" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$AUTH_EMAIL\",\"portal\":\"admin\"}" > /dev/null || true
  sleep 1
  local code=""
  if [ -n "$log" ] && [ -f "$log" ]; then
    code=$(grep -oE '[0-9]{6}' "$log" | tail -1 || true)
  fi
  if [ -z "$code" ]; then
    echo ""
    return
  fi
  VERIFY=$(curl -sf -X POST "$BASE/api/auth/otp/verify" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$AUTH_EMAIL\",\"code\":\"$code\",\"portal\":\"admin\"}" || echo '{}')
  echo "$VERIFY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_token',''))" 2>/dev/null || echo ""
}

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
    TOKEN=$(get_session_token)
    if [ -z "$TOKEN" ]; then
      echo "  ⚠ 无 SESSION_TOKEN 且无法从 OTP 日志获取验证码 — 跳过 confirm"
      echo "    请: export SESSION_TOKEN=<token> 或在 /admin 登录后重试"
    else
      CONF=$(curl -sf -X POST "$BASE/api/confirm/$LEAD_ID" \
        -H "X-Session-Token: $TOKEN" || echo '{"error":"confirm failed"}')
      echo "$CONF" | python3 -m json.tool 2>/dev/null || echo "$CONF"
    fi
  fi
else
  echo "  无到期任务（请 Tab4 查看定时任务）"
fi

echo ""
echo "=== Live Pilot ($COUNTRY) 完成 ==="
echo "  session_id: $SESSION_ID"
echo "  batch_id:   $BATCH_ID"
echo ""
echo "验收脚本:"
echo "  bash scripts/outreach_pilot.sh $BASE"
echo "  bash scripts/trackc_pilot.sh $BASE 50 --no-website"
echo "  bash scripts/kb_pilot.sh $BASE"
