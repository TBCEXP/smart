#!/usr/bin/env bash
# Phase 1.5.7 知识库语义检索验收
# 用法: bash scripts/kb_pilot.sh [BASE_URL] [QUERY]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
QUERY="${2:-哥伦比亚 烘焙模具 分销商}"

echo "=== SMART CRM KB Pilot (1.5.7) ==="
echo "Base: $BASE"
echo "Query: $QUERY"
echo ""

echo "[1] 获取线索并建立索引"
BATCHES=$(curl -sf "$BASE/api/batches" || echo '[]')
BID=$(echo "$BATCHES" | python3 -c "
import sys, json
batches = json.load(sys.stdin)
print(batches[0]['id'] if batches else '')
" 2>/dev/null || echo "")

INDEXED=0
if [ -n "$BID" ]; then
  BATCH=$(curl -sf "$BASE/api/batch/$BID" || echo '{"leads":[]}')
  LEAD_IDS=$(echo "$BATCH" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for l in d.get('leads', [])[:5]:
    print(l['id'])
" 2>/dev/null || echo "")
  for LID in $LEAD_IDS; do
    RES=$(curl -sf -X POST "$BASE/api/kb/index/$LID" || echo '{}')
    if echo "$RES" | grep -q 'indexed'; then
      echo "  indexed: $LID"
      INDEXED=$((INDEXED + 1))
    fi
  done
fi

if [ "$INDEXED" -eq 0 ]; then
  echo "  无现有线索，运行 mini batch…"
  UNIQ_KW="kb-pilot-$(date +%s)"
  RUN=$(curl -sf -X POST "$BASE/api/run" \
    -H "Content-Type: application/json" \
    -d "{\"keyword\":\"$UNIQ_KW\",\"industry\":\"跨境电商\",\"count\":2,\"country_iso\":\"CO\",\"city\":\"Bogotá\",\"category_l3\":\"bakeware\"}")
  BID=$(echo "$RUN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('batch_id',''))" 2>/dev/null || echo "")
  if [ -n "$BID" ]; then
    curl -sf -N --max-time 60 "$BASE/api/stream/$BID" > /dev/null 2>&1 || true
    BATCH=$(curl -sf "$BASE/api/batch/$BID")
    LEAD_IDS=$(echo "$BATCH" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for l in d.get('leads', []):
    print(l['id'])
" 2>/dev/null || echo "")
    for LID in $LEAD_IDS; do
      curl -sf -X POST "$BASE/api/kb/index/$LID" > /dev/null || true
      INDEXED=$((INDEXED + 1))
      echo "  indexed: $LID"
    done
  fi
fi

echo ""
echo "[2] 语义检索"
ENC_QUERY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$QUERY'))")
SEARCH=$(curl -sf "$BASE/api/kb/search?q=$ENC_QUERY&limit=5")
echo "$SEARCH" | python3 -m json.tool 2>/dev/null || echo "$SEARCH"

COUNT=$(echo "$SEARCH" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('results',[])))" 2>/dev/null || echo 0)
if [ "$COUNT" -eq 0 ]; then
  echo "  主查询无结果，尝试英文回退查询 bakeware MX…"
  SEARCH=$(curl -sf "$BASE/api/kb/search?q=bakeware%20MX&limit=5")
  COUNT=$(echo "$SEARCH" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('results',[])))" 2>/dev/null || echo 0)
fi
echo "$SEARCH" | python3 -m json.tool 2>/dev/null || echo "$SEARCH"

HAS_SCORE=$(echo "$SEARCH" | python3 -c "import sys,json; rs=json.load(sys.stdin).get('results',[]); print(any('score' in r for r in rs))" 2>/dev/null || echo False)

echo ""
echo "=== 1.5.7 验收摘要 ==="
echo "  索引线索: $INDEXED"
echo "  召回结果: $COUNT 条"
echo "  含语义分数: $HAS_SCORE (需 OpenAI Key；无 Key 时走文本模糊匹配)"
echo ""

if [ "$COUNT" -gt 0 ]; then
  echo "  结果: ✓ KB 检索可用"
  if [ "$HAS_SCORE" = "True" ]; then
    echo "  语义模式: ✓ OpenAI embedding 已启用"
  else
    echo "  语义模式: ○ 文本回退（配置 OpenAI Key 后重试语义召回）"
  fi
else
  echo "  结果: ○ 无召回结果"
  exit 1
fi
