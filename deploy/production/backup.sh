#!/usr/bin/env bash
# Captures a recoverable production checkpoint without stopping the competition.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/../local/lib/compose.sh"
COMPOSE_FILE=${HIKARI_COMPOSE_FILE:-"$SCRIPT_DIR/docker-compose.production.yml"}
BASE_COMPOSE_FILE=${HIKARI_COMPOSE_BASE_FILE:-"$SCRIPT_DIR/../local/docker-compose.yml"}
COMPOSE_ENV="$SCRIPT_DIR/.compose.env"

[[ -f "$COMPOSE_FILE" ]] || { echo "compose file not found: $COMPOSE_FILE" >&2; exit 1; }
[[ -f "$BASE_COMPOSE_FILE" ]] || { echo "compose base file not found: $BASE_COMPOSE_FILE" >&2; exit 1; }
[[ -f "$COMPOSE_ENV" ]] || { echo "compose environment not found: $COMPOSE_ENV" >&2; exit 1; }

set -a
source "$COMPOSE_ENV"
set +a

BACKUP_DIR=${HIKARI_BACKUP_DIR:-/opt/hikari/backups}
RETENTION_DAYS=${RETENTION_DAYS:-14}

mkdir -p "$BACKUP_DIR"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
archive="$BACKUP_DIR/hikari-$stamp.zip"
snapshot="hikari_$stamp"
repository="hikari_checkpoint_$stamp"
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

compose() {
  hikari_compose \
    -p "${COMPOSE_PROJECT_NAME:-hikari}" \
    -f "$BASE_COMPOSE_FILE" \
    -f "$COMPOSE_FILE" \
    --env-file "$COMPOSE_ENV" \
    "$@"
}

echo "creating checkpoint: $archive"
echo "  - dumping MariaDB"
compose exec -T db mariadb-dump \
  -uctfd -p"$DATABASE_PASSWORD" --single-transaction --routines --triggers ctfd \
  > "$workdir/ctfd.sql"

echo "  - copying uploaded evidence"
compose exec -T ctfd tar -C /var/uploads -cf - . > "$workdir/uploads.tar"

echo "  - snapshotting Elasticsearch indices"
snapshot_indices="competition1,hikari-activity"
compose exec -T elasticsearch curl -fsS \
  "http://localhost:9200/_resolve/index/$snapshot_indices" >/dev/null
compose exec -T elasticsearch curl -fsS -X PUT \
  -H 'Content-Type: application/json' \
  "http://localhost:9200/_snapshot/$repository" \
  -d "{\"type\":\"fs\",\"settings\":{\"location\":\"checkpoints/$snapshot\"}}" >/dev/null
compose exec -T elasticsearch curl -fsS -X PUT \
  -H 'Content-Type: application/json' \
  "http://localhost:9200/_snapshot/$repository/snapshot?wait_for_completion=true" \
  -d "{\"indices\":\"$snapshot_indices\",\"include_global_state\":false}" \
  > "$workdir/elasticsearch-snapshot.json"
tar -C "$BACKUP_DIR/elasticsearch/checkpoints/$snapshot" -cf \
  "$workdir/elasticsearch-repository.tar" .

printf '%s\n' \
  '{' \
  "  \"created_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," \
  '  "database_dump": "ctfd.sql",' \
  '  "uploads_archive": "uploads.tar",' \
  '  "elasticsearch_repository_archive": "elasticsearch-repository.tar",' \
  '  "elasticsearch_snapshot": "snapshot"' \
  '}' > "$workdir/manifest.json"

(cd "$workdir" && zip -q -r "$archive" .)
compose exec -T elasticsearch curl -fsS -X DELETE \
  "http://localhost:9200/_snapshot/$repository" >/dev/null
rm -rf "$BACKUP_DIR/elasticsearch/checkpoints/$snapshot"
find "$BACKUP_DIR" -maxdepth 1 -name 'hikari-*.zip' -mtime +"$RETENTION_DAYS" -delete

size=$(du -h "$archive" | cut -f1)
echo "checkpoint complete: $archive ($size)"
echo "Elasticsearch snapshot included in checkpoint archive."
