#!/usr/bin/env bash
# Restore a QuizForge full backup onto a VPS.
#
# This is intentionally guarded. It can overwrite app files, database data,
# uploads, Nginx config, and Certbot config.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/quizforge/quizforge}"
DOMAIN="${DOMAIN:-quizforge.aabhishek.in}"
WEB_ROOT="${WEB_ROOT:-/var/www/quizforge.aabhishek.in/html}"
BACKUP_ARCHIVE=""
ASSUME_YES=0
INSTALL_PREREQS=0
SKIP_CERTBOT=0
SKIP_NGINX=0

usage() {
  cat <<EOF
Usage: sudo bash deploy/full_restore.sh [options] /path/to/quizforge-full-YYYYmmdd-HHMMSS.tar.gz

Options:
  --yes              Do not ask for confirmation
  --install-prereqs  Install Docker, Nginx, Certbot, Node.js 22, git, curl, rsync
  --skip-certbot     Do not restore /etc/letsencrypt
  --skip-nginx       Do not restore Nginx site files
  -h, --help         Show this help

Environment overrides:
  APP_DIR=$APP_DIR
  DOMAIN=$DOMAIN
  WEB_ROOT=$WEB_ROOT

Recommended fresh-VPS flow:
  sudo mkdir -p /opt/quizforge-backups
  sudo cp quizforge-full-*.tar.gz /opt/quizforge-backups/
  sudo bash deploy/full_restore.sh --install-prereqs /opt/quizforge-backups/quizforge-full-*.tar.gz
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --yes) ASSUME_YES=1 ;;
      --install-prereqs) INSTALL_PREREQS=1 ;;
      --skip-certbot) SKIP_CERTBOT=1 ;;
      --skip-nginx) SKIP_NGINX=1 ;;
      -h|--help) usage; exit 0 ;;
      -*)
        echo "Unknown option: $1" >&2
        usage
        exit 1
        ;;
      *)
        BACKUP_ARCHIVE="$1"
        ;;
    esac
    shift
  done
}

run() {
  printf '\n> %s\n' "$*"
  "$@"
}

confirm() {
  if [[ "$ASSUME_YES" == "1" ]]; then
    return
  fi
  cat <<EOF

This restore can overwrite:
  $APP_DIR
  PostgreSQL database inside Docker Compose
  uploads Docker volume
  Nginx config for $DOMAIN
  Certbot config under /etc/letsencrypt

EOF
  read -r -p "Type RESTORE to continue: " answer
  if [[ "$answer" != "RESTORE" ]]; then
    echo "Restore cancelled."
    exit 1
  fi
}

install_prereqs() {
  if [[ "$INSTALL_PREREQS" != "1" ]]; then
    return
  fi
  apt-get update
  apt-get install -y ca-certificates curl gnupg git nginx certbot python3-certbot-nginx rsync
  if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
  fi
  if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 22 ]]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
  fi
}

extract_backup() {
  if [[ -z "$BACKUP_ARCHIVE" || ! -f "$BACKUP_ARCHIVE" ]]; then
    echo "Backup archive not found: ${BACKUP_ARCHIVE:-<missing>}" >&2
    usage
    exit 1
  fi
  RESTORE_DIR="$(mktemp -d /tmp/quizforge-restore.XXXXXX)"
  tar -C "$RESTORE_DIR" -xzf "$BACKUP_ARCHIVE"
  if [[ ! -f "$RESTORE_DIR/repo.tar.gz" || ! -f "$RESTORE_DIR/db.sql.gz" ]]; then
    echo "Backup archive is missing repo.tar.gz or db.sql.gz" >&2
    exit 1
  fi
}

restore_repo() {
  mkdir -p "$APP_DIR"
  tar -C "$APP_DIR" -xzf "$RESTORE_DIR/repo.tar.gz"
}

start_base_services() {
  cd "$APP_DIR"
  docker compose up -d --build db redis
  docker compose up -d --build api worker
}

restore_database() {
  cd "$APP_DIR"
  docker compose exec -T db psql -U quizforge -d quizforge \
    -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
  gunzip -c "$RESTORE_DIR/db.sql.gz" | docker compose exec -T db psql -U quizforge -d quizforge
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

restore_uploads() {
  if [[ ! -f "$RESTORE_DIR/uploads.tar.gz" ]]; then
    echo "No uploads.tar.gz in backup; skipping uploads restore."
    return
  fi
  local volume
  volume="$(uploads_volume_name)"
  docker volume create "$volume" >/dev/null
  docker run --rm \
    -v "$volume":/data \
    -v "$RESTORE_DIR":/backup \
    alpine sh -c 'rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null || true; tar xzf /backup/uploads.tar.gz -C /data'
}

restore_server_config() {
  if [[ "$SKIP_NGINX" != "1" && -f "$RESTORE_DIR/server/nginx-sites-available-$DOMAIN" ]]; then
    mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
    cp -a "$RESTORE_DIR/server/nginx-sites-available-$DOMAIN" "/etc/nginx/sites-available/$DOMAIN"
    ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
  fi

  if [[ "$SKIP_CERTBOT" != "1" && -f "$RESTORE_DIR/letsencrypt.tar.gz" ]]; then
    tar -C /etc -xzf "$RESTORE_DIR/letsencrypt.tar.gz"
  fi
}

build_frontend() {
  cd "$APP_DIR"
  npm --prefix frontend ci
  npm --prefix frontend run build
  mkdir -p "$WEB_ROOT"
  rsync -a --delete frontend/dist/ "$WEB_ROOT/"
  chown -R www-data:www-data "$(dirname "$WEB_ROOT")" 2>/dev/null || true
}

restart_and_check() {
  cd "$APP_DIR"
  docker compose up -d --build api worker
  nginx -t
  systemctl reload nginx
  curl -fsS http://127.0.0.1:8000/api/health
  curl -fsS "https://$DOMAIN/api/health" || true
}

main() {
  parse_args "$@"
  confirm
  install_prereqs
  extract_backup
  restore_repo
  start_base_services
  restore_database
  restore_uploads
  restore_server_config
  build_frontend
  restart_and_check
  rm -rf "$RESTORE_DIR"
  echo
  echo "Restore complete."
}

main "$@"
