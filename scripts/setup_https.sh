#!/usr/bin/env bash
# RackNerd VPS HTTPS 配置（Certbot + Docker Nginx）
# 用法: sudo bash scripts/setup_https.sh crm.yourdomain.com
set -euo pipefail

DOMAIN="${1:-}"
OPT_DIR="${OPT_DIR:-/opt/smart-crm}"
EMAIL="${CERTBOT_EMAIL:-admin@${DOMAIN}}"

if [ -z "$DOMAIN" ]; then
  echo "用法: sudo bash scripts/setup_https.sh <域名> [邮箱可选通过 CERTBOT_EMAIL=]"
  exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 sudo 运行"
  exit 1
fi

cd "$OPT_DIR"
mkdir -p /var/www/certbot

echo "==> [1/6] 检查 DNS: $DOMAIN"
RESOLVED=$(dig +short "$DOMAIN" 2>/dev/null | head -1 || true)
PUBLIC_IP=$(curl -sf --max-time 5 ifconfig.me 2>/dev/null || curl -sf --max-time 5 icanhazip.com 2>/dev/null || echo "")
echo "  DNS 解析: ${RESOLVED:-未解析}"
echo "  本机公网 IP: ${PUBLIC_IP:-未知}"
if [ -n "$RESOLVED" ] && [ -n "$PUBLIC_IP" ] && [ "$RESOLVED" != "$PUBLIC_IP" ]; then
  echo "  警告: DNS 可能未指向本机，证书申请可能失败"
fi

echo "==> [2/6] 临时 HTTP nginx（用于 ACME）"
cat > "$OPT_DIR/nginx/crm.conf" <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://smart-crm:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }
}
EOF

echo "==> [3/6] 重启 nginx"
docker compose up -d nginx smart-crm

echo "==> [4/6] 申请 Let's Encrypt 证书"
if ! command -v certbot >/dev/null; then
  apt-get update -qq
  apt-get install -y certbot
fi

docker compose stop nginx 2>/dev/null || true
certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" \
  --preferred-challenges http || {
  docker compose up -d nginx
  echo "证书申请失败。请确认 DNS 和 80 端口可达后重试。"
  exit 1
}

echo "==> [5/6] 生成 HTTPS nginx 配置"
sed "s/__DOMAIN__/$DOMAIN/g" "$OPT_DIR/nginx/crm-ssl.conf.template" > "$OPT_DIR/nginx/crm.conf"

echo "==> [6/6] 启动 HTTPS nginx"
# 确保 docker-compose 挂载 letsencrypt（见 docker-compose.yml）
docker compose up -d nginx smart-crm

sleep 3
if curl -sfk "https://$DOMAIN/api/health" | grep -q '"status":"ok"'; then
  echo "✓ HTTPS 就绪: https://$DOMAIN"
elif curl -sf "http://127.0.0.1:8000/api/health" | grep -q ok; then
  echo "✓ 后端正常；外网 HTTPS 请检查防火墙 443"
else
  echo "请检查: docker compose logs nginx --tail 30"
fi

echo ""
echo "证书自动续期:"
echo "  echo '0 3 * * * certbot renew --quiet && docker compose -f $OPT_DIR/docker-compose.yml restart nginx' | sudo tee -a /etc/crontab"
