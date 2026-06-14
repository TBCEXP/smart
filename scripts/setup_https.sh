#!/usr/bin/env bash
# RackNerd VPS HTTPS 一键配置（Certbot + Nginx）
# 用法: sudo bash scripts/setup_https.sh crm.yourdomain.com
set -euo pipefail

DOMAIN="${1:-}"
OPT_DIR="${OPT_DIR:-/opt/smart-crm}"

if [ -z "$DOMAIN" ]; then
  echo "用法: sudo bash scripts/setup_https.sh <域名>"
  echo "示例: sudo bash scripts/setup_https.sh crm.example.com"
  exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 sudo 运行"
  exit 1
fi

echo "==> 配置域名: $DOMAIN"
cd "$OPT_DIR"

echo "==> [1/4] 更新 nginx server_name"
NGINX_CONF="$OPT_DIR/nginx/crm.conf"
if [ -f "$NGINX_CONF" ]; then
  sed -i "s/server_name .*/server_name $DOMAIN;/" "$NGINX_CONF"
  ok_msg="已更新 $NGINX_CONF"
else
  echo "警告: 未找到 nginx/crm.conf"
fi

echo "==> [2/4] 重启 nginx"
docker compose up -d nginx smart-crm
sleep 3

echo "==> [3/4] 安装 certbot（如未安装）"
if ! command -v certbot >/dev/null; then
  apt-get update -qq
  apt-get install -y certbot
fi

echo "==> [4/4] 申请证书"
echo "注意: 域名 $DOMAIN 的 DNS A 记录须已指向本机 IP"
certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN" || {
  echo ""
  echo "证书申请失败。请检查:"
  echo "  1. DNS A 记录是否生效: dig +short $DOMAIN"
  echo "  2. 80 端口是否可从公网访问"
  echo "  3. 防火墙是否放行 80/443"
  exit 1
}

echo ""
echo "==> 挂载证书到 nginx（docker 方式需手动配置 volume）"
echo "证书路径: /etc/letsencrypt/live/$DOMAIN/"
echo ""
echo "请将 nginx/crm.conf 增加 443 server 块，或参考 docs/DEPLOYMENT.md 第六节"
echo "完成后: docker compose restart nginx"
echo ""
echo "验证: curl -sf https://$DOMAIN/api/health"
