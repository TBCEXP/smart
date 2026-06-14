#!/usr/bin/env bash
# 上传工厂目录 PDF 至 Cloudflare R2（通过 SMART CRM 预签名 URL）
# 用法:
#   bash scripts/upload_catalog_r2.sh BASE_URL DOC_ID PDF_FILE SESSION_TOKEN
#   bash scripts/upload_catalog_r2.sh http://127.0.0.1:8000 <doc-uuid> ./catalog.pdf $(grep admin smart-crm/data/auth_emails.log | tail -1)
#
# 前置: Tab2 或 env 配置 r2_account_id / r2_access_key_id / r2_secret_access_key / r2_bucket
set -euo pipefail

BASE="${1:-}"
DOC_ID="${2:-}"
PDF="${3:-}"
TOKEN="${4:-}"

if [ -z "$BASE" ] || [ -z "$DOC_ID" ] || [ -z "$PDF" ] || [ -z "$TOKEN" ]; then
  echo "用法: $0 BASE_URL DOC_ID PDF_FILE SESSION_TOKEN"
  exit 1
fi

if [ ! -f "$PDF" ]; then
  echo "文件不存在: $PDF"
  exit 1
fi

echo ">>> 请求预签名上传 URL"
RESP=$(curl -sf -X POST "$BASE/api/catalog/documents/$DOC_ID/upload-url" \
  -H "Content-Type: application/json" \
  -H "X-Session-Token: $TOKEN" \
  -d '{"update_file_url": true}')

MODE=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('mode',''))")
UPLOAD=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('upload_url') or '')")
FILE_URL=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('file_url') or '')")

if [ "$MODE" = "mock" ] || [ -z "$UPLOAD" ]; then
  echo "R2 未配置或无法生成上传 URL:"
  echo "$RESP" | python3 -m json.tool
  exit 2
fi

echo ">>> PUT $PDF -> R2 ($FILE_URL)"
curl -sf -X PUT "$UPLOAD" \
  -H "Content-Type: application/pdf" \
  --data-binary @"$PDF"

echo ""
echo ">>> 上传完成"
echo "file_url: $FILE_URL"
echo "验证: curl -H 'X-Session-Token: $TOKEN' $BASE/api/catalog/documents/$DOC_ID/download-url"
