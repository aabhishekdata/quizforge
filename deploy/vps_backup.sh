#!/usr/bin/env bash
# Full VPS backup helper.
#
# This is broader than the QuizForge app backup. It captures the practical
# recovery state for a small Ubuntu VPS:
# - system configuration under /etc
# - /home, /root, /opt, /srv, /var/www, and /usr/local
# - common non-Docker database data under /var/lib/mysql, /var/lib/postgresql, /var/lib/redis
# - Docker volumes, Docker metadata, and optional container image archives
# - package lists, crontabs, systemd unit files, firewall state, and service metadata
# - QuizForge PostgreSQL logical dump when the compose project is present
#
# For true whole-machine rollback, also enable provider snapshots/backups
# in Hetzner. This script is the portable recovery copy.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/vps-backups}"
APP_DIR="${APP_DIR:-/opt/quizforge/quizforge}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
INCLUDE_DOCKER_IMAGES="${INCLUDE_DOCKER_IMAGES:-0}"
STAMP="$(date +%Y%m%d-%H%M%S)"
WORK_DIR="$BACKUP_DIR/work-$STAMP"
ARCHIVE="$BACKUP_DIR/vps-full-$STAMP.tar.gz"

usage() {
  cat <<EOF
Usage: sudo bash deploy/vps_backup.sh [options]

Options:
  --include-docker-images  Also save Docker images. This can make the backup very large.
  -h, --help               Show this help.

Environment overrides:
  BACKUP_DIR=$BACKUP_DIR
  APP_DIR=$APP_DIR
  RETENTION_DAYS=$RETENTION_DAYS
  INCLUDE_DOCKER_IMAGES=$INCLUDE_DOCKER_IMAGES

Output:
  $ARCHIVE
  $ARCHIVE.sha256
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --include-docker-images) INCLUDE_DOCKER_IMAGES=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Run as root: sudo bash deploy/vps_backup.sh" >&2
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

tar_if_exists() {
  local archive="$1"
  shift
  local existing=()
  local path
  for path in "$@"; do
    [[ -e "$path" ]] && existing+=("$path")
  done
  if [[ "${#existing[@]}" -gt 0 ]]; then
    tar \
      --one-file-system \
      --xattrs \
      --acls \
      --warning=no-file-changed \
      --exclude='*/node_modules' \
      --exclude='*/.venv' \
      --exclude='*/frontend/dist' \
      --exclude='*/tmp' \
      --exclude='*/.cache' \
      -czf "$archive" \
      "${existing[@]}" || {
        status=$?
        [[ "$status" -eq 1 ]] || exit "$status"
      }
  fi
}

collect_metadata() {
  mkdir -p "$WORK_DIR/metadata"
  hostnamectl > "$WORK_DIR/metadata/hostnamectl.txt" 2>/dev/null || true
  uname -a > "$WORK_DIR/metadata/uname.txt" 2>/dev/null || true
  lsb_release -a > "$WORK_DIR/metadata/lsb-release.txt" 2>/dev/null || true
  ip addr > "$WORK_DIR/metadata/ip-addr.txt" 2>/dev/null || true
  ss -tulpn > "$WORK_DIR/metadata/listening-ports.txt" 2>/dev/null || true
  df -hT > "$WORK_DIR/metadata/df.txt" 2>/dev/null || true
  lsblk -f > "$WORK_DIR/metadata/lsblk.txt" 2>/dev/null || true
  timedatectl > "$WORK_DIR/metadata/timedatectl.txt" 2>/dev/null || true

  dpkg --get-selections > "$WORK_DIR/metadata/dpkg-selections.txt" 2>/dev/null || true
  apt-mark showmanual > "$WORK_DIR/metadata/apt-manual.txt" 2>/dev/null || true
  snap list > "$WORK_DIR/metadata/snap-list.txt" 2>/dev/null || true
  pipx list > "$WORK_DIR/metadata/pipx-list.txt" 2>/dev/null || true

  crontab -l > "$WORK_DIR/metadata/root-crontab.txt" 2>/dev/null || true
  for spool in /var/spool/cron/crontabs/*; do
    [[ -e "$spool" ]] || continue
    cp -a "$spool" "$WORK_DIR/metadata/cron-$(basename "$spool").txt"
  done

  systemctl list-unit-files > "$WORK_DIR/metadata/systemd-unit-files.txt" 2>/dev/null || true
  systemctl list-timers --all > "$WORK_DIR/metadata/systemd-timers.txt" 2>/dev/null || true
  ufw status verbose > "$WORK_DIR/metadata/ufw-status.txt" 2>/dev/null || true
  iptables-save > "$WORK_DIR/metadata/iptables-save.txt" 2>/dev/null || true
  nft list ruleset > "$WORK_DIR/metadata/nft-ruleset.txt" 2>/dev/null || true
}

backup_filesystems() {
  mkdir -p "$WORK_DIR/files"
  echo "Backing up system and website directories..."
  echo "/etc" >> "$WORK_DIR/files/included-paths.txt"
  tar_if_exists "$WORK_DIR/files/etc.tar.gz" /etc
  echo "/home" >> "$WORK_DIR/files/included-paths.txt"
  tar_if_exists "$WORK_DIR/files/home.tar.gz" /home
  echo "/root" >> "$WORK_DIR/files/included-paths.txt"
  tar_if_exists "$WORK_DIR/files/root.tar.gz" /root
  echo "/opt" >> "$WORK_DIR/files/included-paths.txt"
  tar_if_exists "$WORK_DIR/files/opt.tar.gz" /opt
  echo "/srv" >> "$WORK_DIR/files/included-paths.txt"
  tar_if_exists "$WORK_DIR/files/srv.tar.gz" /srv
  echo "/var/www" >> "$WORK_DIR/files/included-paths.txt"
  tar_if_exists "$WORK_DIR/files/var-www.tar.gz" /var/www
  echo "/usr/local" >> "$WORK_DIR/files/included-paths.txt"
  tar_if_exists "$WORK_DIR/files/usr-local.tar.gz" /usr/local
  echo "/var/lib/mysql" >> "$WORK_DIR/files/included-paths.txt"
  tar_if_exists "$WORK_DIR/files/var-lib-mysql.tar.gz" /var/lib/mysql
  echo "/var/lib/postgresql" >> "$WORK_DIR/files/included-paths.txt"
  tar_if_exists "$WORK_DIR/files/var-lib-postgresql.tar.gz" /var/lib/postgresql
  echo "/var/lib/redis" >> "$WORK_DIR/files/included-paths.txt"
  tar_if_exists "$WORK_DIR/files/var-lib-redis.tar.gz" /var/lib/redis
}

backup_docker() {
  mkdir -p "$WORK_DIR/docker/volumes"
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker not installed; skipping Docker backup."
    return
  fi

  docker version > "$WORK_DIR/docker/docker-version.txt" 2>/dev/null || true
  docker compose version > "$WORK_DIR/docker/docker-compose-version.txt" 2>/dev/null || true
  docker ps -a > "$WORK_DIR/docker/containers.txt" 2>/dev/null || true
  docker images > "$WORK_DIR/docker/images.txt" 2>/dev/null || true
  docker network ls > "$WORK_DIR/docker/networks.txt" 2>/dev/null || true
  docker volume ls > "$WORK_DIR/docker/volumes.txt" 2>/dev/null || true
  docker inspect $(docker ps -aq) > "$WORK_DIR/docker/container-inspect.json" 2>/dev/null || true

  local volume
  while read -r volume; do
    [[ -n "$volume" ]] || continue
    echo "Backing up Docker volume: $volume"
    docker run --rm \
      -v "$volume":/data:ro \
      -v "$WORK_DIR/docker/volumes":/backup \
      alpine tar czf "/backup/$volume.tar.gz" -C /data .
  done < <(docker volume ls -q)

  if [[ "$INCLUDE_DOCKER_IMAGES" == "1" ]]; then
    mkdir -p "$WORK_DIR/docker/images"
    docker images --format '{{.Repository}}:{{.Tag}}' \
      | grep -v '<none>' \
      > "$WORK_DIR/docker/image-tags.txt" || true
    if [[ -s "$WORK_DIR/docker/image-tags.txt" ]]; then
      xargs docker save -o "$WORK_DIR/docker/images/docker-images.tar" < "$WORK_DIR/docker/image-tags.txt"
      gzip "$WORK_DIR/docker/images/docker-images.tar"
    fi
  fi
}

backup_quizforge_database() {
  mkdir -p "$WORK_DIR/apps/quizforge"
  if [[ ! -f "$APP_DIR/docker-compose.yml" ]]; then
    echo "QuizForge compose file not found at APP_DIR=$APP_DIR; skipping app pg_dump."
    return
  fi
  (
    cd "$APP_DIR"
    docker compose exec -T db pg_dump -U quizforge -d quizforge
  ) | gzip > "$WORK_DIR/apps/quizforge/db.sql.gz" || {
    echo "QuizForge pg_dump failed; Docker volume backup may still contain database files." >&2
    rm -f "$WORK_DIR/apps/quizforge/db.sql.gz"
  }
}

write_restore_notes() {
  cat > "$WORK_DIR/RESTORE_NOTES.txt" <<'EOF'
VPS restore notes
=================

Best complete rollback:
1. Use a Hetzner snapshot/server backup if available.
2. Use this archive when you need portable recovery or partial restore.

Suggested fresh Ubuntu restore:
1. Install base packages: Docker, Nginx, Certbot, git, rsync.
2. Extract this archive.
3. Restore /etc, /home, /root, /opt, /var/www, and /usr/local archives as needed.
4. Restore Docker volumes from docker/volumes/*.tar.gz.
5. Start Docker Compose projects from their restored /opt directories.
6. Restore logical app database dumps, if included.
7. Run nginx -t and reload Nginx.
8. Verify public health checks.

This archive intentionally excludes virtual filesystems like /proc, /sys, /dev,
/run, and bulky caches. It is not a byte-for-byte disk image.
EOF
}

main() {
  require_root
  run mkdir -p "$BACKUP_DIR"
  run rm -rf "$WORK_DIR"
  run mkdir -p "$WORK_DIR"

  collect_metadata
  backup_filesystems
  backup_docker
  backup_quizforge_database
  write_restore_notes

  tar -C "$WORK_DIR" -czf "$ARCHIVE" .
  sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
  rm -rf "$WORK_DIR"

  find "$BACKUP_DIR" -name 'vps-full-*.tar.gz' -mtime +"$RETENTION_DAYS" -delete
  find "$BACKUP_DIR" -name 'vps-full-*.tar.gz.sha256' -mtime +"$RETENTION_DAYS" -delete

  echo
  echo "VPS backup complete:"
  echo "  $ARCHIVE"
  echo "  $ARCHIVE.sha256"
  echo
  echo "The archive includes website files from /var/www, app files from /opt and /srv,"
  echo "Nginx/Certbot/server config from /etc, and every Docker named volume."
  echo
  echo "Copy both files off the VPS."
}

main "$@"
