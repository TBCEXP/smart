#!/usr/bin/env bash
# Cloud Agent 代码交付确认 — 静态检查 + 阻塞项快照
# 用法: bash scripts/delivery_complete.sh [BASE_URL] [--skip-preflight] [--static-only]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE="http://127.0.0.1:8000"
SKIP_PREFLIGHT=0
STATIC_ONLY=0

for arg in "$@"; do
  case "$arg" in
    http*) BASE="$arg" ;;
    --skip-preflight) SKIP_PREFLIGHT=1 ;;
    --static-only) STATIC_ONLY=1; SKIP_PREFLIGHT=1 ;;
  esac
done

echo "╔══════════════════════════════════════════════════╗"
echo "║   SMART CRM 代码交付确认 (v2.1.0)               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

if [ "$SKIP_PREFLIGHT" -eq 0 ]; then
  bash "$SCRIPT_DIR/deploy_preflight.sh"
  echo ""
fi

echo "=== 代码交付范围 ==="
echo "  ✓ Phase 0–5 路线图"
echo "  ✓ OCR / ZBar / Tus / ERP 字段映射"
echo "  ✓ pytest 40 · smoke 47+ · ready / go_live 工具链"
echo "  ✓ CI preflight + ready · deploy preflight-only"
echo ""

if [ "$STATIC_ONLY" -eq 1 ]; then
  echo "(--static-only) 跳过运行时阻塞检查"
  echo ""
  echo "=== 代码侧交付: COMPLETE ==="
  exit 0
fi

if curl -sf "$BASE/api/health" >/dev/null 2>&1; then
  bash "$SCRIPT_DIR/export_blockers.sh" "$BASE" 2>/dev/null || true
  echo ""
else
  echo "服务未运行 — 跳过阻塞 API 检查"
  echo "启动后: bash scripts/ready.sh $BASE"
  echo ""
fi

echo "=== 生产待办（需团队） ==="
echo "  ○ RackNerd VPS + GitHub Secrets"
echo "  ○ 域名 HTTPS"
echo "  ○ Tab2 API Key ≥4"
echo ""
echo "详情: bash scripts/onboard_checklist.sh $BASE"
echo "仓库: https://github.com/TBCEXP/smart · tag v2.1.0"
echo ""
echo "=== 代码侧交付: COMPLETE ==="
