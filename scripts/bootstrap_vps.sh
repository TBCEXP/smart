#!/usr/bin/env bash
# 全新 RackNerd VPS 一键引导：克隆 → 安装 → 验收
# 用法: curl -fsSL https://raw.githubusercontent.com/TBCEXP/smart/main/scripts/bootstrap_vps.sh | sudo bash
# 或:   sudo bash scripts/bootstrap_vps.sh
set -euo pipefail

REPO="${SMART_REPO:-https://github.com/TBCEXP/smart.git}"
OPT_DIR="${OPT_DIR:-/opt/smart-crm}"
DATA_DIR="${DATA_DIR:-/var/lib/smart-crm}"
BRANCH="${DEPLOY_BRANCH:-main}"

echo "=== SMART CRM VPS Bootstrap ==="
echo "仓库: $REPO"
echo "分支: $BRANCH"
echo ""

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 sudo 运行本脚本"
  exit 1
fi

mkdir -p "$OPT_DIR" "$DATA_DIR"

if [ ! -d "$OPT_DIR/.git" ]; then
  echo "==> 克隆仓库到 $OPT_DIR"
  git clone "$REPO" "$OPT_DIR"
fi

cd "$OPT_DIR"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull origin "$BRANCH"

echo "==> 运行 install.sh"
bash scripts/install.sh

echo ""
echo "=== Bootstrap 完成 ==="
echo ""
echo "后续步骤:"
echo "  1. 浏览器打开 http://$(curl -sf ifconfig.me 2>/dev/null || echo 'VPS_IP'):8000"
echo "  2. Tab2 配置 API Key → 检测连通性"
echo "  3. GitHub Secrets: VPS_HOST / VPS_USER / VPS_SSH_KEY（自动部署）"
echo "  4. sudo bash scripts/setup_https.sh crm.yourdomain.com"
echo "  5. bash scripts/pilot_live.sh http://127.0.0.1:8000"
