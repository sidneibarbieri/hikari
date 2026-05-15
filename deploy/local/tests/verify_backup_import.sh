#!/usr/bin/env bash
# Verifies a legacy .data backup in an isolated Compose project.
# The current local stack is not modified.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$SCRIPT_DIR"

default_zip="$SCRIPT_DIR/../../../data_backup.zip"
ZIP=${1:-$default_zip}
[[ -f "$ZIP" ]] || { echo "usage: $0 <path-to-backup.zip>"; exit 2; }

stamp=$(date +%s)
PROJECT=${HIKARI_IMPORT_PROJECT:-hikariimport${stamp}}
CTFD_PORT=${HIKARI_IMPORT_PORT:-8011}
MAIL_UI_PORT=${HIKARI_IMPORT_MAIL_UI_PORT:-1081}
MAIL_SMTP_PORT=${HIKARI_IMPORT_MAIL_SMTP_PORT:-1026}
CTFD_URL=${CTFD_URL:-http://localhost:${CTFD_PORT}}
COMPOSE_FILE=${COMPOSE_FILE:-$LOCAL_DIR/docker-compose.yml}
COMPOSE=(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT")

cleanup() {
  if [[ "${KEEP_IMPORT_STACK:-0}" != "1" ]]; then
    "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

query_db() {
  "${COMPOSE[@]}" exec -T db \
    mariadb -uctfd -pctfd ctfd -N -B -e "$1" | tr -d '[:space:]'
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
"${COMPOSE[@]}" up -d --build

echo "==> waiting for isolated stack"
COMPOSE_PROJECT_NAME="$PROJECT" CTFD_URL="$CTFD_URL" bash smoke.sh --wait

echo "==> importing backup"
COMPOSE_PROJECT_NAME="$PROJECT" CTFD_URL="$CTFD_URL" bash import_backup.sh "$ZIP" --yes

echo "==> reapplying current automation admin and theme"
COMPOSE_PROJECT_NAME="$PROJECT" CTFD_URL="$CTFD_URL" bash ensure_admin.sh
COMPOSE_PROJECT_NAME="$PROJECT" CTFD_URL="$CTFD_URL" bash apply_theme.sh
COMPOSE_PROJECT_NAME="$PROJECT" CTFD_URL="$CTFD_URL" bash apply_branding.sh
COMPOSE_PROJECT_NAME="$PROJECT" CTFD_URL="$CTFD_URL" bash verify_plugin.sh

users=$(query_db "SELECT COUNT(*) FROM users;")
teams=$(query_db "SELECT COUNT(*) FROM teams;")
challenges=$(query_db "SELECT COUNT(*) FROM challenges;")
solves=$(query_db "SELECT COUNT(*) FROM solves;")
hikari_challenges=$(query_db "SELECT COUNT(*) FROM challenges WHERE type='hikari';")
activity_table=$(query_db "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='ctfd' AND table_name='hikari_activity';")
upload_files=$(docker run --rm -v "${PROJECT}_ctfd-uploads":/uploads:ro alpine \
  sh -c "find /uploads -type f | wc -l" | tr -d '[:space:]')

require_positive "users" "$users"
require_positive "teams" "$teams"
require_positive "challenges" "$challenges"
require_positive "solves" "$solves"
require_positive "hikari challenges" "$hikari_challenges"
require_positive "upload files" "$upload_files"
[[ "$activity_table" == "1" ]] || { echo "FAIL: hikari_activity table missing"; exit 1; }
echo "PASS: hikari_activity table present"

echo
echo "Backup import verified in isolated project: $PROJECT"
