#!/usr/bin/env bash
# 部署前静态检查 — 无需启动服务（本地 / CI / VPS 首次克隆后）
# 用法: bash scripts/deploy_preflight.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PASS=0
WARN=0
FAIL=0

ok()    { echo "  ✓ $1"; PASS=$((PASS+1)); }
warn()  { echo "  ! $1"; WARN=$((WARN+1)); }
fail()  { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "=== SMART CRM 部署前检查 (deploy_preflight) ==="
echo "Root: $ROOT"
echo ""

cd "$ROOT"

echo "[1] 仓库结构"
for f in docker-compose.yml .env.example smart-crm/Dockerfile smart-crm/main.py smart-crm/requirements.txt; do
  if [ -f "$f" ]; then ok "$f"; else fail "missing $f"; fi
done

echo ""
echo "[2] 验收脚本"
for s in go_live.sh deploy_verify.sh release_check.sh upgrade.sh bootstrap_vps.sh prod_onboard.sh ready.sh onboard_checklist.sh export_blockers.sh; do
  if [ -x "scripts/$s" ]; then ok "scripts/$s"; else fail "scripts/$s (not executable)"; fi
done

echo ""
echo "[3] 文档"
for f in docs/HANDOFF.md docs/VPS_ONBOARDING.md docs/DEPLOYMENT.md docs/CHANGELOG.md; do
  if [ -f "$f" ]; then ok "$f"; else fail "missing $f"; fi
done

echo ""
echo "[4] 版本一致性"
for f in .env.example docker-compose.yml smart-crm/main.py; do
  if grep -q '2\.1\.0' "$f" 2>/dev/null; then
    ok "VERSION 2.1.0 in $f"
  else
    warn "VERSION 2.1.0 not found in $f"
  fi
done

echo ""
echo "[5] Docker Compose"
if command -v docker >/dev/null && [ -f docker-compose.yml ]; then
  if docker compose config -q 2>/dev/null; then
    ok "docker compose config valid"
  else
    fail "docker compose config invalid"
  fi
else
  warn "docker unavailable — skip compose config (CI 有 docker-build job)"
fi

echo ""
echo "[6] Python 依赖"
if python3 -c "import pathlib; pathlib.Path('smart-crm/requirements.txt').read_text()" 2>/dev/null; then
  ok "requirements.txt readable"
  if pip install -r smart-crm/requirements.txt --dry-run -q 2>/dev/null; then
    ok "requirements.txt resolvable"
  else
    warn "requirements dry-run skipped or failed"
  fi
else
  fail "requirements.txt unreadable"
fi

echo ""
echo "[7] GitHub Actions"
for wf in .github/workflows/ci.yml .github/workflows/deploy.yml; do
  if [ -f "$wf" ]; then ok "$wf"; else fail "missing $wf"; fi
done

echo ""
echo "=== Preflight: ${PASS} passed, ${WARN} warnings, ${FAIL} failed ==="
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
echo ""
echo "下一步:"
echo "  本地: cd smart-crm && USE_SQLITE=1 uvicorn main:app --port 8000 &"
echo "  验收: bash scripts/go_live.sh http://127.0.0.1:8000"
echo "  VPS:  sudo bash scripts/bootstrap_vps.sh"
