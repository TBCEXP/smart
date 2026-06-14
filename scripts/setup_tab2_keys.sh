#!/usr/bin/env bash
# Tab2 API Key 配置指南 — 生产获客必配项
# 用法: bash scripts/setup_tab2_keys.sh [BASE_URL]
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"

echo "╔══════════════════════════════════════════════════╗"
echo "║   SMART CRM — Tab2 API Key 配置指南              ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

if curl -sf "$BASE/api/health" >/dev/null 2>&1; then
  INT=$(curl -sf "$BASE/api/integrations/status" 2>/dev/null || echo '{}')
  CC=$(echo "$INT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('configured_count',0))" 2>/dev/null || echo 0)
  PR=$(echo "$INT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('production_ready',False))" 2>/dev/null || echo False)
  echo "服务: $BASE"
  echo "已配置: $CC/9 | production_ready=$PR"
  echo ""
  echo "面板: ${BASE}/admin → Tab2"
  echo "探测: curl -X POST ${BASE}/api/integrations/probe"
  echo ""
else
  echo "服务未运行 — 先启动应用再配置 Tab2"
  echo ""
fi

cat <<'EOF'
=== 必配（≥4 → production_ready）===

| Key | 获取地址 | 用途 |
|-----|----------|------|
| Exa | https://exa.ai | Track A 语义搜索 |
| Firecrawl | https://firecrawl.dev | 网页抓取分析 |
| OpenAI | https://platform.openai.com | LLM + KB embedding |
| 飞书 | https://open.feishu.cn | 线索同步（app_id/secret/table） |

=== 推荐 ===

| Key | 用途 |
|-----|------|
| Cloudflare R2 | 目录 PDF + 大文件（account_id/access_key/secret/bucket） |
| Resend | 分享链接邮件 |
| TBCEXP ERP | 订单同步（api_url + token，可选） |

=== 配置步骤 ===

1. 浏览器打开 /admin → 使用 OTP 登录（邮件见 data/auth_emails.log 或 Resend）
2. Tab2 填写 Key → 保存
3. 点击「检测连通性」→ 期望 4/4 live
4. 点击「飞书写入测试」→ 飞书表出现测试行
5. 验收:
   bash scripts/prod_onboard.sh BASE_URL --full
   bash scripts/pilot_live.sh BASE_URL

飞书字段对照: GET /docs/feishu-fields · docs/FEISHU_FIELDS.md
EOF
