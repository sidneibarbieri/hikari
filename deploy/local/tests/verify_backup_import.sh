#!/usr/bin/env bash
# Verifies a legacy .data backup in an isolated Compose project.
# The current local stack is not modified.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"
cd "$LOCAL_DIR"

default_zip="$LOCAL_DIR/../../../data_backup.zip"
ZIP=${1:-$default_zip}
[[ -f "$ZIP" ]] || { echo "usage: $0 <path-to-backup.zip>"; exit 2; }

stamp=$(date +%s)
PROJECT=${HIKARI_IMPORT_PROJECT:-hikariimport${stamp}}
CTFD_PORT=${HIKARI_IMPORT_PORT:-8011}
MAIL_UI_PORT=${HIKARI_IMPORT_MAIL_UI_PORT:-1081}
MAIL_SMTP_PORT=${HIKARI_IMPORT_MAIL_SMTP_PORT:-1026}
CTFD_URL=${CTFD_URL:-http://localhost:${CTFD_PORT}}
COMPOSE_FILE=${COMPOSE_FILE:-$LOCAL_DIR/docker-compose.yml}
compose() {
  hikari_compose -f "$COMPOSE_FILE" -p "$PROJECT" "$@"
}

cleanup() {
  if [[ "${KEEP_IMPORT_STACK:-0}" != "1" ]]; then
    compose down -v --remove-orphans >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

query_db() {
  compose exec -T db \
    mariadb -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" "$HIKARI_DB_NAME" -N -B -e "$1" | tr -d '[:space:]'
}

require_positive() {
  local label=$1 value=$2
  if (( value <= 0 )); then
    echo "FAIL: $label is $value"
    exit 1
  fi
  echo "PASS: $label = $value"
}

export COMPOSE_PROJECT_NAME="$PROJECT"
export CTFD_PORT MAIL_UI_PORT MAIL_SMTP_PORT CTFD_URL

echo "==> starting isolated stack: $PROJECT"
compose up -d --build

echo "==> waiting for isolated stack"
COMPOSE_PROJECT_NAME="$PROJECT" CTFD_URL="$CTFD_URL" bash "$SCRIPT_DIR/smoke.sh" --wait

echo "==> importing backup"
COMPOSE_PROJECT_NAME="$PROJECT" CTFD_URL="$CTFD_URL" bash "$LOCAL_DIR/scripts/import_backup.sh" "$ZIP" --yes

echo "==> reapplying current automation admin and theme"
COMPOSE_PROJECT_NAME="$PROJECT" CTFD_URL="$CTFD_URL" bash "$LOCAL_DIR/scripts/ensure_admin.sh"
COMPOSE_PROJECT_NAME="$PROJECT" CTFD_URL="$CTFD_URL" bash "$LOCAL_DIR/scripts/apply_theme.sh"
COMPOSE_PROJECT_NAME="$PROJECT" CTFD_URL="$CTFD_URL" bash "$LOCAL_DIR/scripts/apply_branding.sh"
COMPOSE_PROJECT_NAME="$PROJECT" CTFD_URL="$CTFD_URL" bash "$SCRIPT_DIR/verify_plugin.sh"

users=$(query_db "SELECT COUNT(*) FROM users;")
teams=$(query_db "SELECT COUNT(*) FROM teams;")
challenges=$(query_db "SELECT COUNT(*) FROM challenges;")
solves=$(query_db "SELECT COUNT(*) FROM solves;")
hikari_challenges=$(query_db "SELECT COUNT(*) FROM challenges WHERE type='hikari';")
activity_table=$(query_db "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='ctfd' AND table_name='hikari_activity';")
upload_files=$(docker run --rm -v "${PROJECT}_ctfd-uploads":/uploads:ro alpine \
  sh -c "find /uploads -type f | wc -l" | tr -d '[:space:]')
competition_events=$(compose exec -T elasticsearch \
  curl -fsS http://localhost:9200/competition1/_count \
  | jq -r '.count')

require_positive "users" "$users"
require_positive "teams" "$teams"
require_positive "challenges" "$challenges"
require_positive "solves" "$solves"
require_positive "hikari challenges" "$hikari_challenges"
require_positive "upload files" "$upload_files"
require_positive "competition events rebuilt from active challenge logs" "$competition_events"
[[ "$activity_table" == "1" ]] || { echo "FAIL: hikari_activity table missing"; exit 1; }
echo "PASS: hikari_activity table present"

echo
echo "Backup import verified in isolated project: $PROJECT"
