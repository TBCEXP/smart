#!/usr/bin/env bash
# 生产阻塞项检查 — VPS/API Key 就绪前一键诊断
# 用法: bash scripts/prod_readiness_check.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
PASS=0
WARN=0
BLOCK=0

ok()    { echo "  ✓ $1"; PASS=$((PASS+1)); }
warn()  { echo "  ! $1"; WARN=$((WARN+1)); }
block() { echo "  ✗ $1"; BLOCK=$((BLOCK+1)); }

echo "╔══════════════════════════════════════════════════╗"
echo "║   SMART CRM 生产就绪诊断                         ║"
echo "╚══════════════════════════════════════════════════╝"
echo "Base: $BASE"
echo ""

echo "[1] 服务健康"
if curl -sf "$BASE/api/health" | grep -q '"status":"ok"'; then
  ok "服务运行中"
  VER=$(curl -sf "$BASE/api/health" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "?")
  echo "     版本: $VER"
else
  block "服务不可达 — 先启动 uvicorn 或 docker compose"
fi

echo ""
echo "[2] API Key / 集成"
INT=$(curl -sf "$BASE/api/integrations/status" 2>/dev/null || echo '{}')
CC=$(echo "$INT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('configured_count',0))" 2>/dev/null || echo 0)
PR=$(echo "$INT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('production_ready',False))" 2>/dev/null || echo False)
if [ "$PR" = "True" ]; then
  ok "production_ready ($CC/9 keys)"
else
  block "production_ready=False ($CC/9) — Tab2 配置 Exa/Firecrawl/OpenAI/飞书"
fi

echo ""
echo "[3] 路线图验收"
for script in smoke_test.sh phase3_verify.sh phase4_verify.sh phase5_verify.sh erp_verify.sh; do
  if bash "$(dirname "$0")/$script" "$BASE" >/dev/null 2>&1; then
    ok "$script"
  else
    warn "$script 有失败项"
  fi
done

echo ""
echo "[4] 生产阻塞清单（需用户提供）"
block "RackNerd VPS IP + GitHub Secrets (VPS_HOST/USER/SSH_KEY)"
block "域名 + DNS → HTTPS (setup_https.sh)"
warn "Cloudflare R2 — 目录 PDF + 大文件实传"
warn "TBCEXP ERP URL/Token — 真实字段对齐（当前 Mock 可用）"
warn "Resend API Key — 分享邮件实发（可选）"

echo ""
echo "=== 诊断: ${PASS} 通过, ${WARN} 警告, ${BLOCK} 阻塞 ==="
echo ""
echo "代码验收:"
echo "  bash scripts/final_acceptance.sh $BASE"
echo ""
echo "VPS 就绪后:"
echo "  sudo bash scripts/bootstrap_vps.sh"
echo "  bash scripts/upgrade.sh"
echo "  bash scripts/onboard_checklist.sh $BASE"
echo "  bash scripts/prod_onboard.sh https://crm.yourdomain.com --full"
echo ""
if [ "$BLOCK" -gt 2 ]; then
  exit 1
fi
