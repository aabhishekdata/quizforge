#!/usr/bin/env bash
# Full QuizForge VPS recovery backup.
#
# Captures the application state needed to rebuild this VPS:
# - PostgreSQL dump
# - uploads Docker volume
# - repo working tree, including .env, excluding bulky build/cache folders
# - Nginx site config
# - Certbot/Let's Encrypt config, when readable
# - crontab and useful server metadata
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/quizforge/quizforge}"
BACKUP_DIR="${BACKUP_DIR:-/opt/quizforge-backups}"
DOMAIN="${DOMAIN:-quizforge.aabhishek.in}"
WEB_ROOT="${WEB_ROOT:-/var/www/quizforge.aabhishek.in/html}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
WORK_DIR="$BACKUP_DIR/work-$STAMP"
ARCHIVE="$BACKUP_DIR/quizforge-full-$STAMP.tar.gz"

usage() {
  cat <<EOF
Usage: sudo bash deploy/full_backup.sh

Environment overrides:
  APP_DIR=$APP_DIR
  BACKUP_DIR=$BACKUP_DIR
  DOMAIN=$DOMAIN
  WEB_ROOT=$WEB_ROOT
  RETENTION_DAYS=$RETENTION_DAYS

Output:
  $ARCHIVE
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

require_app_dir() {
  if [[ ! -f "$APP_DIR/docker-compose.yml" ]]; then
    echo "Cannot find docker-compose.yml in APP_DIR=$APP_DIR" >&2
    echo "Set APP_DIR to the active QuizForge repo directory." >&2
    exit 1
  fi
}

run() {
  printf '\n> %s\n' "$*"
  "$@"
}

copy_if_exists() {
  local source="$1"
  local dest="$2"
  if [[ -e "$source" ]]; then
    mkdir -p "$(dirname "$dest")"
    cp -a "$source" "$dest"
  fi
}

backup_repo() {
  mkdir -p "$WORK_DIR"
  tar \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='node_modules' \
    --exclude='frontend/node_modules' \
    --exclude='frontend/dist' \
    --exclude='tmp' \
    --exclude='output' \
    --exclude='.pip-cache' \
    -C "$APP_DIR" \
    -czf "$WORK_DIR/repo.tar.gz" \
    .
}

backup_database() {
  cd "$APP_DIR"
  docker compose exec -T db pg_dump -U quizforge -d quizforge | gzip > "$WORK_DIR/db.sql.gz"
}

uploads_volume_name() {
  cd "$APP_DIR"
  local api_id
  api_id="$(docker compose ps -q api || true)"
  if [[ -n "$api_id" ]]; then
    docker inspect "$api_id" \
      --format '{{range .Mounts}}{{if eq .Destination "/data/uploads"}}{{.Name}}{{end}}{{end}}'
    return
  fi
  basename "$APP_DIR" | sed 's/$/_uploads/'
}

backup_uploads() {
  local volume
  volume="$(uploads_volume_name)"
  if [[ -z "$volume" ]]; then
    echo "Could not determine uploads volume name; skipping uploads archive." >&2
    return
  fi
  if docker volume inspect "$volume" >/dev/null 2>&1; then
    docker run --rm \
      -v "$volume":/data:ro \
      -v "$WORK_DIR":/backup \
      alpine tar czf /backup/uploads.tar.gz -C /data .
    echo "$volume" > "$WORK_DIR/uploads-volume.txt"
  else
    echo "Uploads volume $volume not found; skipping uploads archive." >&2
  fi
}

backup_server_config() {
  mkdir -p "$WORK_DIR/server"
  copy_if_exists "/etc/nginx/sites-available/$DOMAIN" "$WORK_DIR/server/nginx-sites-available-$DOMAIN"
  copy_if_exists "/etc/nginx/sites-enabled/$DOMAIN" "$WORK_DIR/server/nginx-sites-enabled-$DOMAIN"
  copy_if_exists "/etc/nginx/nginx.conf" "$WORK_DIR/server/nginx.conf"
  copy_if_exists "$WEB_ROOT" "$WORK_DIR/server/web-root"

  if [[ -d /etc/letsencrypt ]]; then
    tar -C /etc -czf "$WORK_DIR/letsencrypt.tar.gz" letsencrypt
  fi

  crontab -l > "$WORK_DIR/server/user-crontab.txt" 2>/dev/null || true
  sudo crontab -l > "$WORK_DIR/server/root-crontab.txt" 2>/dev/null || true
  docker --version > "$WORK_DIR/server/docker-version.txt" 2>/dev/null || true
  docker compose version > "$WORK_DIR/server/docker-compose-version.txt" 2>/dev/null || true
  uname -a > "$WORK_DIR/server/uname.txt" 2>/dev/null || true
  lsb_release -a > "$WORK_DIR/server/lsb-release.txt" 2>/dev/null || true
}

write_manifest() {
  cd "$APP_DIR"
  {
    echo "created_at=$STAMP"
    echo "app_dir=$APP_DIR"
    echo "domain=$DOMAIN"
    echo "web_root=$WEB_ROOT"
    echo "git_commit=$(git rev-parse HEAD 2>/dev/null || true)"
    echo "git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    echo "host=$(hostname)"
  } > "$WORK_DIR/manifest.txt"
}

main() {
  require_app_dir
  run mkdir -p "$BACKUP_DIR"
  run rm -rf "$WORK_DIR"
  run mkdir -p "$WORK_DIR"

  echo "Creating full QuizForge backup..."
  backup_repo
  backup_database
  backup_uploads
  backup_server_config
  write_manifest

  tar -C "$WORK_DIR" -czf "$ARCHIVE" .
  sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
  rm -rf "$WORK_DIR"

  find "$BACKUP_DIR" -name 'quizforge-full-*.tar.gz' -mtime +"$RETENTION_DAYS" -delete
  find "$BACKUP_DIR" -name 'quizforge-full-*.tar.gz.sha256' -mtime +"$RETENTION_DAYS" -delete

  echo
  echo "Backup complete:"
  echo "  $ARCHIVE"
  echo "  $ARCHIVE.sha256"
  echo
  echo "Copy these files off the VPS, for example:"
  echo "  scp abhi@$DOMAIN:$ARCHIVE ."
  echo "  scp abhi@$DOMAIN:$ARCHIVE.sha256 ."
}

main "$@"
