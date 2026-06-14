#!/usr/bin/env bash
# 导出生产阻塞 JSON — 供团队 / CI 归档
# 用法: bash scripts/export_blockers.sh [BASE_URL] [OUTPUT_FILE]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
OUT="${2:-production-blockers-$(date +%Y%m%d-%H%M).json}"

echo "=== SMART CRM 生产阻塞导出 ==="
echo "Base: $BASE"
echo ""

READY=$(curl -sf "$BASE/api/system/readiness" 2>/dev/null || echo '{}')
if ! echo "$READY" | grep -q production_blockers; then
  echo "✗ 无法获取 production_blockers — 服务是否运行？"
  exit 1
fi

echo "$READY" | OUT="$OUT" python3 -c "
import json, os, sys
d = json.load(sys.stdin)
out = {
    'production_ready': d.get('production_ready'),
    'production_blockers': d.get('production_blockers', {}),
    'integrations': {
        'configured_count': d.get('integrations', {}).get('configured_count'),
        'production_ready': d.get('integrations', {}).get('production_ready'),
    },
}
path = os.environ['OUT']
with open(path, 'w') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
b = out['production_blockers']
print('✓ 已写入:', path)
print('  blocking_count:', b.get('blocking_count'))
print('  live_ready:', b.get('live_ready'))
for item in b.get('detected', []):
    mark = '✓' if item.get('done') else ('✗' if item.get('blocking') else '○')
    print(f\"  {mark} {item.get('label')}\")
"
