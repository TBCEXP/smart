#!/usr/bin/env bash
# 第零期部署前检查清单 — 科学验收，不跳步上线
set -euo pipefail

PASS=0
FAIL=0
WARN=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }
warn() { echo "  ! $1"; WARN=$((WARN+1)); }

echo "=== SMART CRM 第零期 Preflight ==="
echo ""

# 1. 系统资源
echo "[1] 系统资源"
if command -v free >/dev/null; then
  MEM_MB=$(free -m | awk '/^Mem:/{print $2}')
  if [ "$MEM_MB" -ge 3500 ]; then ok "内存 ${MEM_MB}MB (≥4GB 推荐)"
  elif [ "$MEM_MB" -ge 1500 ]; then warn "内存 ${MEM_MB}MB (2GB 勉强，建议 Postgres 外置)"
  else fail "内存 ${MEM_MB}MB 不足"; fi
else warn "无法检测内存"; fi

if command -v df >/dev/null; then
  DISK_AVAIL=$(df -BG / | awk 'NR==2{print $4}' | tr -d G)
  if [ "$DISK_AVAIL" -ge 30 ]; then ok "根分区可用 ${DISK_AVAIL}GB"
  else warn "根分区可用 ${DISK_AVAIL}GB，大文件须走对象存储"; fi
else warn "无法检测磁盘"; fi

# 2. Docker
echo ""
echo "[2] 容器环境"
if command -v docker >/dev/null; then ok "Docker 已安装"
else warn "Docker 未安装（RackNerd 生产环境必须）"; fi

if [ -f docker-compose.yml ]; then ok "docker-compose.yml 存在"
else fail "缺少 docker-compose.yml"; fi

# 3. 目录结构
echo ""
echo "[3] 程序/数据分离"
for d in /opt/smart-crm /var/lib/smart-crm/smart-crm-data; do
  if [ -d "$d" ]; then ok "目录 $d 存在"
  else warn "目录 $d 未创建（install.sh 会创建）"; fi
done

# 4. 配置与密钥
echo ""
echo "[4] API 配置（data/config.json）"
DATA_DIR="${DATA_DIR:-/var/lib/smart-crm/smart-crm-data}"
if [ ! -f "$DATA_DIR/config.json" ] && [ -f smart-crm/data/config.json ]; then
  DATA_DIR="smart-crm/data"
fi
if [ -f "$DATA_DIR/config.json" ]; then
  ok "config.json 存在"
  for key in exa_api_key firecrawl_api_key openai_api_key feishu_app_id; do
    if grep -q "$key" "$DATA_DIR/config.json" 2>/dev/null; then
      ok "  字段 $key 已配置"
    else
      warn "  字段 $key 未配置（Tab2 填写）"
    fi
  done
else
  warn "config.json 不存在 — 首次启动后于 Tab2 配置"
fi

# 5. 服务健康
echo ""
echo "[5] 服务健康"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/health}"
if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then ok "GET $HEALTH_URL"
else warn "服务未运行或不可达"; fi

# 6. 安全
echo ""
echo "[6] 安全"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/api/config -H "Content-Type: application/json" -d '{}' 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "401" ]; then ok "未认证写配置返回 401"
else warn "写配置返回 HTTP $HTTP_CODE（期望 401）"; fi

# 7. 文档
echo ""
echo "[7] 实施路线图"
if [ -f docs/IMPLEMENTATION_ROADMAP.md ]; then ok "docs/IMPLEMENTATION_ROADMAP.md 存在"
else warn "缺少实施路线图"; fi

echo ""
echo "=== 结果: ${PASS} 通过, ${WARN} 警告, ${FAIL} 失败 ==="
if [ "$FAIL" -gt 0 ]; then
  echo "请先解决失败项再上线生产。"
  exit 1
fi
echo "警告项可在试点期逐步补齐。第零期通过后进入 1.5 期 MX 试点。"
