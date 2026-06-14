#!/usr/bin/env bash
# Phase 0.7 每日数据备份 — 打包 /var/lib/smart-crm（或本地 DATA_DIR）
# 用法: sudo bash scripts/backup_daily.sh [DATA_DIR] [BACKUP_DIR]
# Cron 示例: 0 3 * * * /opt/smart-crm/scripts/backup_daily.sh >> /var/log/smart-crm-backup.log 2>&1
set -euo pipefail

DATA_DIR="${1:-/var/lib/smart-crm}"
BACKUP_DIR="${2:-/var/backups/smart-crm}"
STAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE="$BACKUP_DIR/smart-crm_${STAMP}.tar.gz"
KEEP_DAYS="${KEEP_DAYS:-14}"

if [ ! -d "$DATA_DIR" ]; then
  echo "ERROR: DATA_DIR not found: $DATA_DIR"
  exit 1
fi

mkdir -p "$BACKUP_DIR"
tar -czf "$ARCHIVE" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")"
echo "Backup created: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

find "$BACKUP_DIR" -name 'smart-crm_*.tar.gz' -mtime +"$KEEP_DAYS" -delete 2>/dev/null || true
echo "Pruned backups older than ${KEEP_DAYS} days"
