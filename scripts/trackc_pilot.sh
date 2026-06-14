#!/usr/bin/env bash
# Phase 1.5.6 Track C 试点：CSV 导入 + 域名匹配验收
# 用法: bash scripts/trackc_pilot.sh [BASE_URL] [ROW_COUNT] [--no-website|--with-website]
#   --no-website   默认：CSV 不含 website，触发 Exa 域名匹配（生产验收）
#   --with-website CSV 含预填域名（快速 Mock 演示）
set -euo pipefail

BASE="http://127.0.0.1:8000"
ROWS=50
COUNTRY="${COUNTRY:-MX}"
HS="${HS:-732393}"
WITH_WEBSITE=0

for arg in "$@"; do
  case "$arg" in
    http*) BASE="$arg" ;;
    --no-website) WITH_WEBSITE=0 ;;
    --with-website) WITH_WEBSITE=1 ;;
    [0-9]*) ROWS="$arg" ;;
  esac
done

TMP_CSV=$(mktemp /tmp/trackc_pilot.XXXXXX.csv)
cleanup() { rm -f "$TMP_CSV"; }
trap cleanup EXIT

MODE=$([ "$WITH_WEBSITE" -eq 1 ] && echo "with-website (mock)" || echo "no-website (Exa match)")

echo "=== SMART CRM Track C Pilot (1.5.6) ==="
echo "Base: $BASE | Rows: $ROWS | Country: $COUNTRY | Mode: $MODE"
echo ""

echo "[1] 生成 ${ROWS} 行测试 CSV"
if [ "$WITH_WEBSITE" -eq 1 ]; then
  {
    echo "company_name,website,hs_code,email,volume"
    for i in $(seq 1 "$ROWS"); do
      printf 'Importador Cocina %03d,https://import-cocina-%03d.example.com,732393,import%03d@example.com,%s\n' \
        "$i" "$i" "$i" "$(( 500 + i * 10 ))"
    done
  } > "$TMP_CSV"
else
  {
    echo "company_name,hs_code,email,volume"
    for i in $(seq 1 "$ROWS"); do
      printf 'Importador Cocina %03d,732393,import%03d@example.com,%s\n' \
        "$i" "$i" "$(( 500 + i * 10 ))"
    done
  } > "$TMP_CSV"
fi
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
echo "$STATS" | python3 -m json.tool 2>/dev/null | head -60 || echo "$STATS"

IMPORTED_DB=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('track_c',{}).get('imported',0))" 2>/dev/null || echo 0)
MATCHED_DB=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('track_c',{}).get('domain_matched',0))" 2>/dev/null || echo 0)
RATE=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('track_c',{}).get('match_rate',0))" 2>/dev/null || echo 0)
MILESTONE=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('milestones',{}).get('1_5_6_track_c',False))" 2>/dev/null || echo False)

echo ""
echo "=== Track C 验收摘要 ==="
echo "  本次导入: $IMPORTED 条"
echo "  本次 Exa 匹配: $MATCHED 个域名"
echo "  库内导入: $IMPORTED_DB 条"
echo "  库内匹配: $MATCHED_DB 个域名"
echo "  匹配率:   ${RATE} (目标 >0.60)"
echo "  里程碑:   $MILESTONE"
echo "  目标:     CSV 50 条 + 域名匹配率 >60%"

if [ "$MILESTONE" = "True" ]; then
  echo "  结果:     ✓ 1.5.6 达标"
elif python3 -c "import sys; r=float(sys.argv[1]); sys.exit(0 if r >= 0.60 else 1)" "$RATE" 2>/dev/null; then
  echo "  结果:     ✓ 匹配率达标（导入量可能 <50）"
else
  echo "  结果:     ○ 未达标（配置 Exa 后用 --no-website 重试）"
fi
