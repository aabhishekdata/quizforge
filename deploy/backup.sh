#!/usr/bin/env bash
# Nightly backup: pg_dump + uploads, keep 14 days locally.
# Add to crontab: 0 3 * * * /opt/quizforge/deploy/backup.sh
# Optionally rsync $BACKUP_DIR to a Hetzner Storage Box.
set -euo pipefail
BACKUP_DIR=/opt/quizforge-backups
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d-%H%M)
cd /opt/quizforge
docker compose exec -T db pg_dump -U quizforge quizforge | gzip > "$BACKUP_DIR/db-$STAMP.sql.gz"
docker run --rm -v quizforge_uploads:/data -v "$BACKUP_DIR":/backup alpine \
  tar czf "/backup/uploads-$STAMP.tar.gz" -C /data .
find "$BACKUP_DIR" -name '*.gz' -mtime +14 -delete
echo "Backup $STAMP done"
