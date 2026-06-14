#!/usr/bin/env bash
# 生产阻塞清单 — API 动态检测 + 人工待办命令
# 用法: bash scripts/onboard_checklist.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"

echo "╔══════════════════════════════════════════════════╗"
echo "║   SMART CRM 生产上线待办清单                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

if curl -sf "$BASE/api/health" >/dev/null 2>&1; then
  VER=$(curl -sf "$BASE/api/health" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "?")
  READY=$(curl -sf "$BASE/api/system/readiness" 2>/dev/null || echo '{}')
  echo "服务: $BASE (version $VER)"
  echo "$READY" | BASE="$BASE" python3 -c "
import sys, json, os
d = json.load(sys.stdin)
b = d.get('production_blockers', {})
base = os.environ.get('BASE', 'http://127.0.0.1:8000')
print('production_ready:', d.get('production_ready'))
print('live_ready:', b.get('live_ready'))
print('blocking_count:', b.get('blocking_count'))
print('')
print('## 自动检测项')
for item in b.get('detected', []):
    mark = '✓' if item.get('done') else ('✗' if item.get('blocking') else '○')
    print(f\"  {mark} {item.get('label')}: {item.get('hint', '')}\")
print('')
print('## 人工待办')
for item in b.get('manual', []):
    print(f\"  [ ] {item.get('label')}: {item.get('hint', '')}\")
if b.get('live_ready'):
    print('')
    print(f'✓ 可执行: bash scripts/prod_onboard.sh {base} --full')
" 2>/dev/null || true
  echo ""
else
  echo "服务: 未运行 ($BASE)"
  echo "启动: cd smart-crm && USE_SQLITE=1 uvicorn main:app --port 8000 &"
  echo ""
fi

cat <<'EOF'
## 操作步骤

### 1. VPS
```bash
sudo bash scripts/bootstrap_vps.sh
bash scripts/upgrade.sh
bash scripts/ready.sh http://127.0.0.1:8000
```

### 2. GitHub Secrets
`VPS_HOST` · `VPS_USER` · `VPS_SSH_KEY` → 仓库 Settings → Actions
```bash
bash scripts/setup_github_deploy.sh [VPS_IP]
```

### 3. HTTPS
```bash
sudo bash scripts/setup_https.sh crm.yourdomain.com
sudo bash scripts/setup_backup_cron.sh
```

### 4. Tab2 API Key（≥4）
/admin → Tab2 → Exa / Firecrawl / OpenAI / 飞书 →「检测连通性」

### 5. 全量验收
```bash
bash scripts/go_live.sh https://crm.yourdomain.com
bash scripts/prod_onboard.sh https://crm.yourdomain.com --full
bash scripts/acceptance_report.sh https://crm.yourdomain.com
```

详见: docs/VPS_ONBOARDING.md · docs/HANDOFF.md
快速入口: bash scripts/production_start.sh [BASE_URL] [VPS_IP]
EOF
