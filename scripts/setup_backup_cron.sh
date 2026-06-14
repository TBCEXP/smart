#!/usr/bin/env bash
# 安装每日数据备份 cron（Phase 0.7）
# 用法: sudo bash scripts/setup_backup_cron.sh
set -euo pipefail

OPT_DIR="${OPT_DIR:-/opt/smart-crm}"
LOG_FILE="${BACKUP_LOG:-/var/log/smart-crm-backup.log}"
CRON_SCHEDULE="${BACKUP_CRON:-0 3 * * *}"
CRON_CMD="$CRON_SCHEDULE $OPT_DIR/scripts/backup_daily.sh >> $LOG_FILE 2>&1"

if [ "$(id -u)" -ne 0 ]; then
  echo "请使用 sudo 运行"
  exit 1
fi

mkdir -p /var/backups/smart-crm
touch "$LOG_FILE"
chmod 644 "$LOG_FILE"

CURRENT=$(crontab -l 2>/dev/null || true)
if echo "$CURRENT" | grep -qF "backup_daily.sh"; then
  echo "已存在 backup_daily cron 条目，更新中…"
  CURRENT=$(echo "$CURRENT" | grep -vF "backup_daily.sh")
fi

(echo "$CURRENT"; echo "$CRON_CMD") | crontab -

echo "✓ 已安装 cron:"
echo "  $CRON_CMD"
echo ""
echo "手动测试: sudo bash $OPT_DIR/scripts/backup_daily.sh"
echo "查看日志: tail -f $LOG_FILE"
