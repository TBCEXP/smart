#!/usr/bin/env bash
# Phase 1.5.6 Track C 试点：CSV 导入 + 域名匹配验收
# 用法: bash scripts/trackc_pilot.sh [BASE_URL] [ROW_COUNT]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
ROWS="${2:-50}"
COUNTRY="${COUNTRY:-MX}"
HS="${HS:-732393}"
TMP_CSV=$(mktemp /tmp/trackc_pilot.XXXXXX.csv)

cleanup() { rm -f "$TMP_CSV"; }
trap cleanup EXIT

echo "=== SMART CRM Track C Pilot (1.5.6) ==="
echo "Base: $BASE | Rows: $ROWS | Country: $COUNTRY"
echo ""

echo "[1] 生成 ${ROWS} 行测试 CSV"
{
  echo "company_name,website,hs_code,email,volume"
  for i in $(seq 1 "$ROWS"); do
    printf 'Importador Cocina %03d,https://import-cocina-%03d.example.com,732393,import%03d@example.com,%s\n' \
      "$i" "$i" "$i" "$(( 500 + i * 10 ))"
  done
} > "$TMP_CSV"
echo "  写入: $TMP_CSV ($(wc -l < "$TMP_CSV") 行含表头)"

echo ""
echo "[2] 导入 CSV"
IMPORT=$(curl -sf -X POST \
  "$BASE/api/import/csv?country_iso=$COUNTRY&hs_codes=$HS&source=trackc_pilot" \
  -F "file=@$TMP_CSV")
echo "$IMPORT" | python3 -m json.tool 2>/dev/null || echo "$IMPORT"
IMPORTED=$(echo "$IMPORT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('imported',0))" 2>/dev/null || echo 0)

echo ""
echo "[3] 域名匹配 (Exa / Mock)"
MATCH=$(curl -sf -X POST "$BASE/api/import/match-domains")
echo "$MATCH" | python3 -m json.tool 2>/dev/null || echo "$MATCH"
MATCHED=$(echo "$MATCH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('matched',0))" 2>/dev/null || echo 0)

echo ""
echo "[4] 试点看板统计"
STATS=$(curl -sf "$BASE/api/stats/overview")
echo "$STATS" | python3 -m json.tool 2>/dev/null | head -50 || echo "$STATS"

IMPORTED_DB=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('track_c',{}).get('imported',0))" 2>/dev/null || echo 0)
MATCHED_DB=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('track_c',{}).get('domain_matched',0))" 2>/dev/null || echo 0)
RATE=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('track_c',{}).get('match_rate',0))" 2>/dev/null || echo 0)

echo ""
echo "=== Track C 验收摘要 ==="
echo "  本次导入: $IMPORTED 条"
echo "  本次匹配: $MATCHED 个域名"
echo "  库内导入: $IMPORTED_DB 条"
echo "  库内匹配: $MATCHED_DB 个域名"
echo "  匹配率:   ${RATE} (目标 >0.60)"
echo "  目标:     CSV 50 条 + 域名匹配率 >60%"

if python3 -c "import sys; r=float(sys.argv[1]); sys.exit(0 if r >= 0.60 else 1)" "$RATE" 2>/dev/null; then
  echo "  结果:     ✓ 1.5.6 达标"
else
  echo "  结果:     ○ 未达标（Mock 模式下无域名记录时属正常，配置 Exa 后重试）"
fi
