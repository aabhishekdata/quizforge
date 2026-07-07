#!/usr/bin/env bash
# Interactive VPS deploy helper for QuizForge.
set -euo pipefail

DOMAIN="${DOMAIN:-quizforge.aabhishek.in}"
WEB_ROOT="${WEB_ROOT:-/var/www/quizforge.aabhishek.in/html}"
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
MODE=""
DRY_RUN=0
SKIP_NPM_CI=0
SKIP_SMOKE=0

usage() {
  cat <<EOF
Usage: bash deploy/update_vps.sh [options]

Options:
  --full             Pull, rebuild backend, build/publish frontend, reload Nginx
  --frontend-only    Pull, build/publish frontend, reload Nginx
  --backend-only     Pull and rebuild backend containers only
  --dry-run          Show commands without running them
  --skip-npm-ci      Use existing node_modules and skip npm ci
  --skip-smoke       Skip curl smoke tests
  -h, --help         Show this help

Environment overrides:
  DOMAIN=$DOMAIN
  WEB_ROOT=$WEB_ROOT
  BRANCH=$BRANCH
  REMOTE=$REMOTE
EOF
}

run() {
  printf '\n> %s\n' "$*"
  if [[ "$DRY_RUN" == "0" ]]; then
    "$@"
  fi
}

run_shell() {
  printf '\n> %s\n' "$*"
  if [[ "$DRY_RUN" == "0" ]]; then
    bash -lc "$*"
  fi
}

require_repo_root() {
  if [[ ! -f docker-compose.yml || ! -d backend || ! -d frontend ]]; then
    echo "Run this from the QuizForge repo root, the folder containing docker-compose.yml, backend/, and frontend/." >&2
    exit 1
  fi
}

choose_mode() {
  cat <<EOF

QuizForge deploy

1) Full deploy        Pull + backend rebuild + frontend build/publish + Nginx reload
2) Frontend only      Pull + frontend build/publish + Nginx reload
3) Backend only       Pull + backend rebuild
4) Dry-run full       Print the full deploy commands without running them
5) Quit

EOF
  read -r -p "Choose an option [1-5]: " choice
  case "$choice" in
    1) MODE="full" ;;
    2) MODE="frontend" ;;
    3) MODE="backend" ;;
    4) MODE="full"; DRY_RUN=1 ;;
    5) exit 0 ;;
    *) echo "Invalid choice: $choice" >&2; exit 1 ;;
  esac
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --full) MODE="full" ;;
      --frontend-only) MODE="frontend" ;;
      --backend-only) MODE="backend" ;;
      --dry-run) DRY_RUN=1 ;;
      --skip-npm-ci) SKIP_NPM_CI=1 ;;
      --skip-smoke) SKIP_SMOKE=1 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
    esac
    shift
  done
}

pull_code() {
  run git fetch "$REMOTE" "$BRANCH"
  run git checkout "$BRANCH"
  run git pull --ff-only "$REMOTE" "$BRANCH"
  run git rev-parse --short HEAD
}

deploy_backend() {
  run docker compose up -d --build api worker
}

deploy_frontend() {
  if [[ "$SKIP_NPM_CI" == "0" ]]; then
    run npm --prefix frontend ci
  fi
  run npm --prefix frontend run build
  run sudo mkdir -p "$WEB_ROOT"
  run sudo rsync -a --delete frontend/dist/ "$WEB_ROOT/"
  run sudo nginx -t
  run sudo systemctl reload nginx
}

smoke_tests() {
  if [[ "$SKIP_SMOKE" == "1" ]]; then
    return
  fi
  run curl -fsS "http://127.0.0.1:8000/api/health"
  run curl -fsS "https://$DOMAIN/api/health"
  run curl -fsSI "https://$DOMAIN/demo"
  run_shell "curl -fsS https://$DOMAIN/ | grep -E 'assets/index-.*\\.js'"
}

main() {
  parse_args "$@"
  require_repo_root
  if [[ -z "$MODE" ]]; then
    choose_mode
  fi

  echo "Mode: $MODE"
  echo "Domain: $DOMAIN"
  echo "Web root: $WEB_ROOT"
  echo "Branch: $REMOTE/$BRANCH"
  [[ "$DRY_RUN" == "1" ]] && echo "Dry run: yes"

  pull_code
  case "$MODE" in
    full)
      deploy_backend
      deploy_frontend
      ;;
    frontend)
      deploy_frontend
      ;;
    backend)
      deploy_backend
      ;;
    *)
      echo "Invalid mode: $MODE" >&2
      exit 1
      ;;
  esac
  smoke_tests
  echo
  echo "Deploy complete."
}

main "$@"
