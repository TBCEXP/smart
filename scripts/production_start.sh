#!/usr/bin/env bash
# 生产上线入口 — 串联交付确认、待办清单、部署与 Key 配置指南
# 用法: bash scripts/production_start.sh [BASE_URL] [VPS_IP]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE="${1:-http://127.0.0.1:8000}"
VPS_IP="${2:-}"

echo "╔══════════════════════════════════════════════════╗"
echo "║   SMART CRM 生产上线入口 (production_start)    ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

bash "$SCRIPT_DIR/delivery_complete.sh" "$BASE" --skip-preflight 2>/dev/null || \
  bash "$SCRIPT_DIR/delivery_complete.sh" --static-only

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash "$SCRIPT_DIR/onboard_checklist.sh" "$BASE" 2>/dev/null | head -35

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " GitHub 自动部署"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash "$SCRIPT_DIR/setup_github_deploy.sh" ${VPS_IP:+"$VPS_IP"}

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Tab2 API Key"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash "$SCRIPT_DIR/setup_tab2_keys.sh" "$BASE" 2>/dev/null | tail -25

echo ""
echo "=== 生产上线顺序 ==="
echo "  1. bash scripts/bootstrap_vps.sh          # VPS root"
echo "  2. bash scripts/setup_github_deploy.sh  # GitHub Secrets"
echo "  3. sudo bash scripts/setup_https.sh crm.domain.com"
echo "  4. Tab2 配置 Key → prod_onboard --full"
echo "  5. bash scripts/go_live.sh https://crm.domain.com"
