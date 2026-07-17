#!/usr/bin/env bash
# Best-effort full VPS restore helper.
#
# This restores a vps-full-*.tar.gz archive created by vps_backup.sh.
# It is intentionally explicit and guarded because it can overwrite critical
# system directories and Docker volume data.
set -euo pipefail

ARCHIVE=""
RESTORE_ROOT=0
RESTORE_DOCKER=0
INSTALL_PREREQS=0
ASSUME_YES=0
RESTORE_DIR=""

usage() {
  cat <<'EOF'
Usage: sudo bash deploy/vps_restore.sh [options] /path/to/vps-full-YYYYmmdd-HHMMSS.tar.gz

Options:
  --install-prereqs  Install Docker, Nginx, Certbot, git, curl, rsync, Node.js 22
  --restore-root     Restore system, website, app, and common database directory archives
  --restore-docker   Restore Docker volumes from the backup
  --yes              Skip the RESTORE confirmation prompt
  -h, --help         Show this help

Common fresh-VPS flow:
  sudo bash deploy/vps_restore.sh --install-prereqs --restore-root --restore-docker /opt/vps-backups/vps-full-*.tar.gz

Safer partial inspection:
  sudo bash deploy/vps_restore.sh /opt/vps-backups/vps-full-*.tar.gz
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-prereqs) INSTALL_PREREQS=1 ;;
    --restore-root) RESTORE_ROOT=1 ;;
    --restore-docker) RESTORE_DOCKER=1 ;;
    --yes) ASSUME_YES=1 ;;
    -h|--help) usage; exit 0 ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
    *) ARCHIVE="$1" ;;
  esac
  shift
done

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Run as root: sudo bash deploy/vps_restore.sh" >&2
    exit 1
  fi
}

confirm() {
  if [[ "$ASSUME_YES" == "1" ]]; then
    return
  fi
  cat <<EOF

This restore can overwrite system files and Docker volume data.

Archive: $ARCHIVE
Restore root directories: $RESTORE_ROOT
Restore Docker volumes:   $RESTORE_DOCKER
Install prerequisites:    $INSTALL_PREREQS

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

extract_archive() {
  if [[ -z "$ARCHIVE" || ! -f "$ARCHIVE" ]]; then
    echo "Backup archive not found: ${ARCHIVE:-<missing>}" >&2
    usage
    exit 1
  fi
  RESTORE_DIR="$(mktemp -d /tmp/vps-restore.XXXXXX)"
  tar -C "$RESTORE_DIR" -xzf "$ARCHIVE"
  echo "Extracted backup to $RESTORE_DIR"
}

restore_root_dirs() {
  if [[ "$RESTORE_ROOT" != "1" ]]; then
    return
  fi
  local item
  for item in etc home root opt srv var-www usr-local var-lib-mysql var-lib-postgresql var-lib-redis; do
    local archive="$RESTORE_DIR/files/$item.tar.gz"
    [[ -f "$archive" ]] || continue
    echo "Restoring $archive to /"
    tar -C / --xattrs --acls -xzf "$archive"
  done
}

restore_docker_volumes() {
  if [[ "$RESTORE_DOCKER" != "1" ]]; then
    return
  fi
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed; cannot restore Docker volumes." >&2
    exit 1
  fi
  shopt -s nullglob
  local archive
  for archive in "$RESTORE_DIR"/docker/volumes/*.tar.gz; do
    local volume
    volume="$(basename "$archive" .tar.gz)"
    echo "Restoring Docker volume: $volume"
    docker volume create "$volume" >/dev/null
    docker run --rm \
      -v "$volume":/data \
      -v "$(dirname "$archive")":/backup \
      alpine sh -c "rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null || true; tar xzf /backup/$(basename "$archive") -C /data"
  done
}

print_next_steps() {
  cat <<EOF

Restore extraction complete.

Useful next steps:
  systemctl daemon-reload
  systemctl restart docker
  nginx -t && systemctl reload nginx

For QuizForge, if restored under /opt/quizforge/quizforge:
  cd /opt/quizforge/quizforge
  docker compose up -d --build db redis api worker
  curl http://127.0.0.1:8000/api/health

Backup contents remain available at:
  $RESTORE_DIR

Review RESTORE_NOTES.txt inside that directory for manual recovery notes.
EOF
}

main() {
  require_root
  confirm
  install_prereqs
  extract_archive
  restore_root_dirs
  restore_docker_volumes
  print_next_steps
}

main "$@"
